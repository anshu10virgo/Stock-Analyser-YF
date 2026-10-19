"""Query the provenance and diagnostics of the current local scan."""

from __future__ import annotations

from collections.abc import Mapping

from stock_analyser.application.queries.get_scan_summary import get_scan_summary


def get_data_health(
    state: Mapping,
    *,
    snapshot_identity: str | None = None,
) -> dict:
    return {
        **get_scan_summary(state),
        "metrics": state.get("scan_metrics", {}),
        "snapshot_identity": snapshot_identity,
    }
