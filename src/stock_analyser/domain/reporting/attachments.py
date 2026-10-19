"""Pure report attachment specifications and batching decisions."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

from stock_analyser.domain.reporting.models import ChartSnapshotSpec


SAFE_ATTACHMENT_BYTES = 12 * 1024 * 1024
T = TypeVar("T")


def chart_snapshot_spec(symbol: str, cross_date=None) -> ChartSnapshotSpec:
    return ChartSnapshotSpec(
        symbol=symbol,
        title=f"{symbol} — Maximum available price history",
        cross_date=cross_date,
    )


def attachment_batches(
    items: Sequence[T],
    packaged_size: Callable[[list[T]], int],
    *,
    max_bytes: int = SAFE_ATTACHMENT_BYTES,
) -> list[list[T]]:
    if max_bytes <= 0:
        raise ValueError("Archive size limit must be positive")
    batches: list[list[T]] = []
    current: list[T] = []
    for item in items:
        candidate = [*current, item]
        if current and packaged_size(candidate) > max_bytes:
            batches.append(current)
            current = [item]
        else:
            current = candidate
    if current:
        batches.append(current)
    return batches


__all__ = [
    "SAFE_ATTACHMENT_BYTES",
    "attachment_batches",
    "chart_snapshot_spec",
]
