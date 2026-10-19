"""Allow-listed, copied application state exposed to the agent runtime."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from stock_analyser.application.context import ApplicationContext
from stock_analyser.application.queries import get_scan_summary, get_stock_status


@dataclass(frozen=True)
class ExecutionContext:
    """Agent-facing wrapper around the bounded application context contract."""

    application: ApplicationContext

    @classmethod
    def from_application_context(
        cls, context: ApplicationContext
    ) -> "ExecutionContext":
        return cls(context)

    @classmethod
    def from_application_state(
        cls, state: Mapping[str, Any]
    ) -> "ExecutionContext":
        """Compatibility boundary that immediately copies allow-listed state."""
        return cls(ApplicationContext.from_session_state(state))

    def as_mapping(self) -> Mapping[str, Any]:
        return self.application.as_mapping()

    def get(self, key: str, default: Any = None) -> Any:
        return self.application.get(key, default)

    @property
    def snapshot_identity(self) -> str | None:
        return self.application.snapshot_identity


def _records(frame: object, columns: list[str], limit: int = 5) -> list[dict]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    available = [column for column in columns if column in frame.columns]
    if not available:
        return []
    selected = frame.loc[:, available].head(limit)
    return selected.where(pd.notna(selected), None).to_dict("records")


def build_local_context(
    source: Mapping[str, Any] | ApplicationContext | ExecutionContext,
    stock_query: str = "",
) -> str:
    """Serialize bounded local state for a hosted model without network access."""
    if isinstance(source, ExecutionContext):
        context = source
    elif isinstance(source, ApplicationContext):
        context = ExecutionContext.from_application_context(source)
    else:
        context = ExecutionContext.from_application_state(source)
    state = context.as_mapping()
    summary = {
        "active_strategy": dict(
            state.get("scan_settings") or state.get("backtest_settings") or {}
        ),
        "scan_summary": get_scan_summary(state),
        "requested_stock": get_stock_status(state, stock_query),
        "post_golden_cross": _records(
            state.get("scan_results"),
            [
                "symbol",
                "company_name",
                "industry",
                "strategy",
                "short_ma_slope",
                "price_above_long_ma_percent",
            ],
        ),
        "impending_golden_cross": _records(
            state.get("scan_impending_results"),
            [
                "symbol",
                "company_name",
                "industry",
                "impending_gap_percent",
                "short_ma_slope",
                "long_ma_slope",
            ],
        ),
        "failed_stocks": _records(
            state.get("scan_failed_results"), ["symbol", "stage", "reason"]
        ),
        "backtest_results": _records(
            state.get("backtest_results"),
            ["Stock", "Company", "Cross date", "Signal date", "Entry", "P/E", "1Y"],
        ),
    }
    return json.dumps(summary, default=str)


__all__ = ["ExecutionContext", "build_local_context"]
