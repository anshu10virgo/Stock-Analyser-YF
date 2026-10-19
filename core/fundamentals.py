"""Compatibility export for the Yahoo fundamentals adapter.

New code should import ``YahooFundamentalsProvider`` from
``stock_analyser.infrastructure.yahoo``.
"""

from stock_analyser.infrastructure.yahoo.fundamentals import (
    YahooFundamentalsProvider,
)

Fundamentals = YahooFundamentalsProvider

__all__ = ["Fundamentals", "YahooFundamentalsProvider"]
