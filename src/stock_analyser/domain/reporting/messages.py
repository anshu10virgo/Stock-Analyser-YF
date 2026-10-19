"""Pure report subject and body construction."""

from stock_analyser.domain.reporting.models import ReportContext, ReportMessageContent


def message_content(
    context: ReportContext,
    *,
    part_number: int,
    part_count: int,
) -> ReportMessageContent:
    if part_count < 1 or not 1 <= part_number <= part_count:
        raise ValueError("Report part must be within the total part count")
    suffix = f" — Part {part_number} of {part_count}" if part_count > 1 else ""
    scan_time = context.scan_time
    return ReportMessageContent(
        subject=f"Stock Analyser scan report — {scan_time:%d %b %Y}{suffix}",
        body=(
            "Completed Stock Analyser report.\n\n"
            f"Post Golden Cross stocks: {context.counts.post_cross}\n"
            f"Impending Golden Cross stocks: {context.counts.impending}\n"
            f"Scan time: {scan_time:%d %b %Y, %I:%M %p}\n"
            f"Report part: {part_number} of {part_count}\n"
        ),
    )


__all__ = ["message_content"]
