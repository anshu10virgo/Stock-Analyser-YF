"""Compatibility export for Yahoo-backed industry valuation.

New code should import from ``stock_analyser.infrastructure.yahoo``.
"""

from stock_analyser.infrastructure.yahoo.industry_valuation import (
    YahooIndustryValuationService,
)

IndustryValuationService = YahooIndustryValuationService

__all__ = ["IndustryValuationService", "YahooIndustryValuationService"]
