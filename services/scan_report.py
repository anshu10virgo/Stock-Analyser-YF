"""Build and email completed scan reports without changing scan outcomes."""

from __future__ import annotations

import io
import re
import smtplib
import zipfile
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage

import pandas as pd
from PIL import Image, ImageDraw


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SAFE_ATTACHMENT_BYTES = 12 * 1024 * 1024
EMAIL_PATTERN = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")

OPTIONAL_FILTER_LABELS = {
    "relative_industry_pe": "Relative Industry P/E",
    "historical_stock_pe": "P/E vs. Historical Stock P/E",
    "peg_ratio": "PEG Ratio",
    "profit_growth": "Multi-Period Profit Growth",
    "eps_growth": "Multi-Period EPS Growth",
    "sales_growth": "Multi-Period Sales / Revenue Growth",
    "return_on_equity": "Return on Equity (ROE)",
    "debt_to_equity": "Debt-to-Equity (D/E) Ratio",
    "market_cap": "Market Capitalisation Buckets",
}

SETTING_LABELS = (
    ("stock_market", "Stock market"),
    ("market_data_source", "Market-data source"),
    ("stock_count", "Stocks analysed"),
    ("adjusted_prices", "Use adjusted prices"),
    ("short_ma", "Short-term moving average (days)"),
    ("long_ma", "Long-term moving average (days)"),
    ("cross_age", "Golden Cross maximum age (calendar days)"),
    (
        "min_long_ma_decline_duration",
        "Minimum high-to-trough decline duration (trading sessions)",
    ),
    ("min_long_ma_decline", "Minimum Long MA decline from 52-week high (%)"),
    ("max_price_premium", "Maximum price above Long MA (%)"),
    ("include_impending_crosses", "Include Impending Golden Cross"),
    ("impending_max_gap_pct", "Maximum Short-to-Long MA gap (%)"),
    (
        "pre_cross_validation_sessions",
        "Pre-cross validation period (trading sessions)",
    ),
)


@dataclass(frozen=True)
class MailConfiguration:
    """Credentials and transport details supplied by deployment secrets."""

    username: str
    password: str
    host: str = SMTP_HOST
    port: int = SMTP_PORT


def parse_recipients(raw_recipients: str) -> tuple[str, ...]:
    """Validate, trim, and de-duplicate comma-separated email addresses."""
    candidates = [value.strip() for value in raw_recipients.split(",") if value.strip()]
    invalid = [value for value in candidates if not EMAIL_PATTERN.fullmatch(value)]
    if invalid:
        raise ValueError("Invalid email address: " + ", ".join(invalid))
    if not candidates:
        raise ValueError("Enter at least one recipient email address")
    return tuple(dict.fromkeys(candidates))


def filter_rows(settings: dict, scan_time: datetime) -> pd.DataFrame:
    """Create the auditable first worksheet for one completed scan."""
    rows = [{"Setting": "Scan date and time", "Value": scan_time.isoformat()}]
    for key, label in SETTING_LABELS:
        value = settings.get(key, "Not recorded")
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        rows.append({"Setting": label, "Value": value})

    selected = settings.get("optional_filters", ())
    rows.append(
        {
            "Setting": "Optional filters selected",
            "Value": len(selected),
        }
    )
    for index, configured in enumerate(selected, start=1):
        key = configured.get("key", "")
        label = OPTIONAL_FILTER_LABELS.get(key, key or "Unknown")
        rows.append({"Setting": f"Optional filter {index}", "Value": label})
        for field, value in configured.items():
            if field == "key":
                continue
            if isinstance(value, (list, tuple)):
                value = ", ".join(map(str, value)) or "None"
            rows.append(
                {
                    "Setting": f"Optional filter {index} — {field.replace('_', ' ').title()}",
                    "Value": "Not set" if value is None else value,
                }
            )
    return pd.DataFrame(rows)


def _export_results(frame: pd.DataFrame) -> pd.DataFrame:
    """Make raw scanner output readable and safe for an Excel worksheet."""
    exported = frame.copy()
    if "market_cap" in exported:
        exported["market_cap"] = pd.to_numeric(
            exported["market_cap"], errors="coerce"
        ).div(10_000_000)
        exported.rename(columns={"market_cap": "Market Cap (₹ Cr)"}, inplace=True)
    exported.rename(
        columns={
            column: column.replace("_", " ").title()
            for column in exported.columns
            if column != "Market Cap (₹ Cr)"
        },
        inplace=True,
    )
    for column in exported.columns:
        exported[column] = exported[column].map(
            lambda value: ", ".join(map(str, value))
            if isinstance(value, (list, tuple))
            else value
        )
    return exported


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
        filter_rows(settings, scan_time).to_excel(
            writer, sheet_name="Filters", index=False
        )
        _export_results(post_cross).to_excel(
            writer, sheet_name="Post Golden Cross", index=False
        )
        _export_results(impending).to_excel(
            writer, sheet_name="Impending Golden Cross", index=False
        )
        for worksheet in writer.sheets.values():
            worksheet.autofit()
    return output.getvalue()


def build_price_chart_png(
    symbol: str,
    chart_data: pd.DataFrame,
    cross_date=None,
) -> bytes:
    """Render a compact maximum-period price/MA snapshot for email."""
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

    draw.text((left, 25), f"{symbol} — Maximum available price history", fill="#182033")
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

    if cross_date is not None and pd.notna(cross_date):
        positions = chart_data.index.searchsorted(pd.Timestamp(cross_date))
        if positions < len(chart_data):
            cross_x = left + (positions / count) * plot_width
            draw.line(
                (cross_x, top, cross_x, top + plot_height),
                fill="#D64545",
                width=2,
            )
            draw.text(
                (min(cross_x + 8, width - 260), top + 8),
                f"Golden Cross {pd.Timestamp(cross_date):%d %b %Y}",
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
    if max_bytes <= 0:
        raise ValueError("Archive size limit must be positive")
    archives: list[bytes] = []
    current: list[tuple[str, bytes]] = []

    def compress(images):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for filename, payload in images:
                archive.writestr(filename, payload)
        return output.getvalue()

    for image in chart_images:
        candidate = compress([*current, image])
        if current and len(candidate) > max_bytes:
            archives.append(compress(current))
            current = [image]
        else:
            current.append(image)
    if current:
        archives.append(compress(current))
    return archives


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
    messages = []
    for index in range(parts):
        message = EmailMessage()
        suffix = f" — Part {index + 1} of {parts}" if parts > 1 else ""
        message["Subject"] = f"Stock Analyser scan report — {scan_time:%d %b %Y}{suffix}"
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message.set_content(
            "Completed Stock Analyser report.\n\n"
            f"Post Golden Cross stocks: {post_count}\n"
            f"Impending Golden Cross stocks: {impending_count}\n"
            f"Scan time: {scan_time:%d %b %Y, %I:%M %p}\n"
            f"Report part: {index + 1} of {parts}\n"
        )
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
    """Send every prepared report part over one authenticated SMTP session."""
    with smtplib.SMTP_SSL(
        configuration.host,
        configuration.port,
        timeout=30,
    ) as smtp:
        smtp.login(configuration.username, configuration.password)
        for message in messages:
            smtp.send_message(message)
