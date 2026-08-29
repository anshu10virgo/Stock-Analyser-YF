"""Typed historical backtest records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


HORIZON_SESSIONS = {"1W": 5, "2W": 10, "3W": 15, "1M": 21, "3M": 63, "6M": 126, "1Y": 252}


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
