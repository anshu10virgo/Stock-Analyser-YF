"""Pure report data, content, and attachment decisions."""

from stock_analyser.domain.reporting.attachments import SAFE_ATTACHMENT_BYTES, attachment_batches, chart_snapshot_spec
from stock_analyser.domain.reporting.messages import message_content
from stock_analyser.domain.reporting.models import ChartSnapshotSpec, ReportContext, ReportCounts, ReportMessageContent
from stock_analyser.domain.reporting.recipients import EMAIL_PATTERN, parse_recipients
from stock_analyser.domain.reporting.workbook import OPTIONAL_FILTER_LABELS, SETTING_LABELS, export_results, filter_records, workbook_frames

__all__ = [
    "ChartSnapshotSpec", "EMAIL_PATTERN", "OPTIONAL_FILTER_LABELS", "ReportContext",
    "ReportCounts", "ReportMessageContent", "SAFE_ATTACHMENT_BYTES", "SETTING_LABELS",
    "attachment_batches", "chart_snapshot_spec", "export_results", "filter_records",
    "message_content", "parse_recipients", "workbook_frames",
]
