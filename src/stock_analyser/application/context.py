"""Bounded application state exposed to queries and agent tools."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import pandas as pd


CONTEXT_KEYS = (
    "scan_results",
    "scan_impending_results",
    "scan_failed_results",
    "backtest_results",
    "scan_settings",
    "backtest_settings",
    "selected_symbols",
    "stock_count",
    "scan_time",
    "scan_metrics",
    "selected_market_data_source",
)


def _copy_value(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return value.copy(deep=True)
    if isinstance(value, dict):
        return {key: _copy_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_value(item) for item in value)
    return value


@dataclass(frozen=True)
class ApplicationContext:
    """Read-only snapshot of state approved for application queries."""

    _values: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_session_state(
        cls, session_state: Mapping[str, Any]
    ) -> "ApplicationContext":
        values = {
            key: _copy_value(session_state[key])
            for key in CONTEXT_KEYS
            if key in session_state
        }
        return cls(MappingProxyType(values))

    def as_mapping(self) -> Mapping[str, Any]:
        return self._values

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    @property
    def snapshot_identity(self) -> str | None:
        settings = self._values.get("scan_settings", {})
        metadata = (
            settings.get("market_data_snapshot", {})
            if isinstance(settings, Mapping)
            else {}
        )
        return (
            metadata.get("snapshot_id")
            or metadata.get("generated_at")
            or metadata.get("last_trading_date")
        )
