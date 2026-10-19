"""Compatibility exports for snapshot-backed infrastructure adapters.

New code should import from ``stock_analyser.infrastructure.r2``.
"""

from stock_analyser.infrastructure.r2.repository import (
    PRICE_COLUMNS,
    RepositoryFundamentalsProvider,
    RepositoryHistoryProvider,
    RepositoryIndustryValuationService,
    RepositoryScreenerProvider,
    SnapshotUnavailableError,
)

__all__ = [
    "PRICE_COLUMNS",
    "RepositoryFundamentalsProvider",
    "RepositoryHistoryProvider",
    "RepositoryIndustryValuationService",
    "RepositoryScreenerProvider",
    "SnapshotUnavailableError",
]
