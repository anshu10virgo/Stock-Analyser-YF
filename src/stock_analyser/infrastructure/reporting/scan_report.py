"""Build and email completed scan reports without changing scan outcomes."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from email.message import EmailMessage

import pandas as pd
from PIL import Image, ImageDraw
from stock_analyser.infrastructure.data_services import SNAPSHOT_SOURCE, snapshot_source_label
from stock_analyser.domain.reporting import (
    SAFE_ATTACHMENT_BYTES,
    ReportContext,
    ReportCounts,
    attachment_batches,
    chart_snapshot_spec,
    export_results,
    filter_records,
    message_content,
    workbook_frames,
)
from stock_analyser.infrastructure.smtp.mailer import (
    MailConfiguration,
    SmtpMailer,
)


def _reported_source_label(settings: dict) -> str | None:
    source = settings.get("market_data_source")
    if source not in {SNAPSHOT_SOURCE, "Git snapshot"}:
        return None
    is_cloud = settings.get("market_data_snapshot", {}).get("access_mode") == "cloud_snapshot"
    return snapshot_source_label(is_cloud)


def filter_rows(settings: dict, scan_time: datetime) -> pd.DataFrame:
    """Create the auditable first worksheet for one completed scan."""
    return pd.DataFrame(
        filter_records(
            settings,
            scan_time,
            market_data_source_label=_reported_source_label(settings),
        )
    )


def _export_results(frame: pd.DataFrame) -> pd.DataFrame:
    """Make raw scanner output readable and safe for an Excel worksheet."""
    return export_results(frame)


def build_workbook(
    settings: dict,
    scan_time: datetime,
    post_cross: pd.DataFrame,
    impending: pd.DataFrame,
) -> bytes:
    """Return an XLSX workbook with Filters as the first worksheet."""
    output = io.BytesIO()
    with pd.ExcelWriter(
        output,
        engine="xlsxwriter",
        datetime_format="yyyy-mm-dd hh:mm:ss",
    ) as writer:
        frames = workbook_frames(
            settings,
            scan_time,
            post_cross,
            impending,
            market_data_source_label=_reported_source_label(settings),
        )
        for sheet_name, frame in frames.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
        for worksheet in writer.sheets.values():
            worksheet.autofit()
    return output.getvalue()


def build_price_chart_png(
    symbol: str,
    chart_data: pd.DataFrame,
    cross_date=None,
) -> bytes:
    """Render a compact maximum-period price/MA snapshot for email."""
    specification = chart_snapshot_spec(symbol, cross_date)
    width, height = 1440, 720
    left, top, right, bottom = 90, 80, 30, 80
    image = Image.new("RGB", (width, height), "#F7F9FC")
    draw = ImageDraw.Draw(image)
    plot_width = width - left - right
    plot_height = height - top - bottom
    series = {
        "Close": (pd.to_numeric(chart_data["Close"], errors="coerce"), "#26324B"),
        "Short MA": (
            pd.to_numeric(chart_data["MA_SHORT"], errors="coerce"),
            "#16A085",
        ),
        "Long MA": (
            pd.to_numeric(chart_data["MA_LONG"], errors="coerce"),
            "#E67E22",
        ),
    }
    available = pd.concat([values for values, _ in series.values()]).dropna()
    if available.empty:
        raise ValueError(f"No chart values are available for {symbol}")
    minimum, maximum = float(available.min()), float(available.max())
    span = maximum - minimum or 1.0
    count = max(len(chart_data) - 1, 1)

    def point(index, value):
        x = left + (index / count) * plot_width
        y = top + ((maximum - value) / span) * plot_height
        return x, y

    draw.text((left, 25), specification.title, fill="#182033")
    for grid_index in range(6):
        y = top + (grid_index / 5) * plot_height
        value = maximum - (grid_index / 5) * span
        draw.line((left, y, width - right, y), fill="#DCE2EC", width=1)
        draw.text((10, y - 7), f"{value:,.2f}", fill="#667085")

    for label, (values, colour) in series.items():
        points = [
            point(index, float(value))
            for index, value in enumerate(values)
            if pd.notna(value)
        ]
        if len(points) > 1:
            draw.line(points, fill=colour, width=3)

    if specification.cross_date is not None and pd.notna(specification.cross_date):
        positions = chart_data.index.searchsorted(pd.Timestamp(specification.cross_date))
        if positions < len(chart_data):
            cross_x = left + (positions / count) * plot_width
            draw.line(
                (cross_x, top, cross_x, top + plot_height),
                fill="#D64545",
                width=2,
            )
            draw.text(
                (min(cross_x + 8, width - 260), top + 8),
                f"Golden Cross {pd.Timestamp(specification.cross_date):%d %b %Y}",
                fill="#D64545",
            )

    start_date = pd.Timestamp(chart_data.index.min()).strftime("%d %b %Y")
    end_date = pd.Timestamp(chart_data.index.max()).strftime("%d %b %Y")
    draw.text((left, height - 50), start_date, fill="#667085")
    draw.text((width - right - 80, height - 50), end_date, fill="#667085")
    legend_x = left
    for label, (_, colour) in series.items():
        draw.line((legend_x, height - 22, legend_x + 28, height - 22), fill=colour, width=3)
        draw.text((legend_x + 36, height - 30), label, fill="#344054")
        legend_x += 150

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def build_chart_archives(
    chart_images: list[tuple[str, bytes]],
    max_bytes: int = SAFE_ATTACHMENT_BYTES,
) -> list[bytes]:
    """Compress charts into bounded ZIP parts without dropping any image."""
    def compress(images):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for filename, payload in images:
                archive.writestr(filename, payload)
        return output.getvalue()

    batches = attachment_batches(
        chart_images,
        lambda images: len(compress(images)),
        max_bytes=max_bytes,
    )
    return [compress(batch) for batch in batches]


def build_messages(
    recipients: tuple[str, ...],
    sender: str,
    scan_time: datetime,
    post_count: int,
    impending_count: int,
    workbook: bytes,
    chart_archives: list[bytes],
) -> list[EmailMessage]:
    """Create numbered report messages; the workbook is attached to part one."""
    parts = max(1, len(chart_archives))
    context = ReportContext(
        scan_time=scan_time,
        counts=ReportCounts(post_cross=post_count, impending=impending_count),
    )
    messages = []
    for index in range(parts):
        content = message_content(
            context,
            part_number=index + 1,
            part_count=parts,
        )
        message = EmailMessage()
        message["Subject"] = content.subject
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message.set_content(content.body)
        if index == 0:
            message.add_attachment(
                workbook,
                maintype="application",
                subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename="stock_analyser_scan_report.xlsx",
            )
        if chart_archives:
            message.add_attachment(
                chart_archives[index],
                maintype="application",
                subtype="zip",
                filename=f"price_charts_part_{index + 1}.zip",
            )
        messages.append(message)
    return messages


def send_messages(
    messages: list[EmailMessage],
    configuration: MailConfiguration,
) -> None:
    """Compatibility function delegating transport to the SMTP adapter."""
    SmtpMailer(configuration).send(messages)
