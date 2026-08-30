"""Bounded, locally derived context for Ticksy responses."""

from __future__ import annotations

import json
from collections.abc import Mapping

import pandas as pd

from services.assistant_tools import active_strategy, scan_summary, stock_status


def _records(frame: object, columns: list[str], limit: int = 5) -> list[dict]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    available = [column for column in columns if column in frame.columns]
    if not available:
        return []
    selected = frame.loc[:, available].head(limit)
    return selected.where(pd.notna(selected), None).to_dict("records")


def build_local_context(session_state: Mapping, stock_query: str = "") -> str:
    """Create a small JSON-like local context with no provider/network access."""
    summary = {
        "active_strategy": active_strategy(session_state),
        "scan_summary": scan_summary(session_state),
        "requested_stock": stock_status(session_state, stock_query),
        "post_golden_cross": _records(session_state.get("scan_results"), ["symbol", "company_name", "industry", "strategy", "short_ma_slope", "price_above_long_ma_percent"]),
        "impending_golden_cross": _records(session_state.get("scan_impending_results"), ["symbol", "company_name", "industry", "impending_gap_percent", "short_ma_slope", "long_ma_slope"]),
        "failed_stocks": _records(session_state.get("scan_failed_results"), ["symbol", "stage", "reason"]),
        "backtest_results": _records(session_state.get("backtest_results"), ["Stock", "Company", "Cross date", "Signal date", "Entry", "P/E", "1Y"]),
    }
    return json.dumps(summary, default=str)
