"""Compatibility exports for Yahoo infrastructure adapters.

New code should import from ``stock_analyser.infrastructure.yahoo``.
"""

from stock_analyser.infrastructure.yahoo.providers import (
    YahooFinanceClassificationProvider,
    YahooFinanceHistoryProvider,
    YahooFinanceIndustryProvider,
    YahooFinanceMarketCapProvider,
)

__all__ = [
    "YahooFinanceClassificationProvider",
    "YahooFinanceHistoryProvider",
    "YahooFinanceIndustryProvider",
    "YahooFinanceMarketCapProvider",
]
