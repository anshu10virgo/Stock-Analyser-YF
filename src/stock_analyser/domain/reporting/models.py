"""Typed provider- and presentation-independent report specifications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ChartSnapshotSpec:
    symbol: str
    title: str
    cross_date: object | None = None


@dataclass(frozen=True)
class ReportMessageContent:
    subject: str
    body: str


@dataclass(frozen=True)
class ReportCounts:
    post_cross: int
    impending: int


@dataclass(frozen=True)
class ReportContext:
    scan_time: datetime
    counts: ReportCounts


__all__ = [
    "ChartSnapshotSpec",
    "ReportContext",
    "ReportCounts",
    "ReportMessageContent",
]
