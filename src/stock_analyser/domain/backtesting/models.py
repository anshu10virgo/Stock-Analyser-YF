"""Typed provider-independent historical backtest outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from stock_analyser.domain.backtesting.horizons import HORIZON_SESSIONS


@dataclass(frozen=True)
class BacktestSignal:
    symbol: str
    cross_date: datetime
    signal_date: datetime
    entry_date: datetime
    entry_price: float
    returns: dict[str, float | None]
    pe: float | None = None
    pe_date: datetime | None = None


@dataclass
class BacktestRun:
    signals: list[BacktestSignal] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ReturnSummary:
    signal_count: int
    observed_count: int
    average_return: float | None
    median_return: float | None


__all__ = ["BacktestRun", "BacktestSignal", "HORIZON_SESSIONS", "ReturnSummary"]
