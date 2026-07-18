"""Industry P/E benchmarks calculated from live Yahoo Finance peer groups."""

from __future__ import annotations

import logging
from copy import deepcopy
from numbers import Real
from statistics import median

from providers.yahoo_finance import YahooFinanceIndustryProvider


logger = logging.getLogger(__name__)


class IndustryValuationService:
    """Calculate and cache NSE-only industry P/E benchmarks for one scan."""

    def __init__(self, provider=None):
        self.provider = provider or YahooFinanceIndustryProvider()
        self._cache = {}
        self._metrics = {"requests": 0, "cache_hits": 0, "failures": 0}

    @staticmethod
    def empty_result():
        """Return a stable unavailable-result contract for scan datasets."""
        return {
            "industry_weighted_pe": None,
            "industry_median_pe": None,
            "industry_peer_count": 0,
        }

    @staticmethod
    def _qualifying_nse_quotes(quotes):
        """Keep one NSE listing per profitable peer with usable market data."""
        valid_quotes = []
        for quote in quotes:
            symbol = quote.get("symbol", "")
            market_cap = quote.get("marketCap")
            trailing_pe = quote.get("trailingPE")
            if (
                not symbol.endswith(".NS")
                or not isinstance(market_cap, Real)
                or not isinstance(trailing_pe, Real)
                or market_cap <= 0
                or trailing_pe <= 0
            ):
                continue
            valid_quotes.append(quote)
        return valid_quotes

    def valuation_for(self, industry):
        """Return weighted and median P/E for an industry, without blocking scans."""
        if not industry:
            return self.empty_result()
        if industry in self._cache:
            self._metrics["cache_hits"] += 1
            return self._cache[industry].copy()

        try:
            self._metrics["requests"] += 1
            quotes = self.provider.industry_quotes(industry)
            peers = self._qualifying_nse_quotes(quotes)
            if not peers:
                result = self.empty_result()
            else:
                market_cap = sum(quote["marketCap"] for quote in peers)
                implied_earnings = sum(
                    quote["marketCap"] / quote["trailingPE"] for quote in peers
                )
                result = {
                    "industry_weighted_pe": round(market_cap / implied_earnings, 2),
                    "industry_median_pe": round(median(quote["trailingPE"] for quote in peers), 2),
                    "industry_peer_count": len(peers),
                }
        except Exception as error:
            self._metrics["failures"] += 1
            logger.warning("Industry valuation unavailable for %s: %s", industry, error)
            result = self.empty_result()

        self._cache[industry] = result
        return result.copy()

    def metrics(self):
        """Return observable peer-data request outcomes for the scan run."""
        return deepcopy(self._metrics)

    def begin_scan(self):
        """Start a fresh benchmark snapshot while preserving per-scan caching."""
        self._cache.clear()
        self._metrics = {"requests": 0, "cache_hits": 0, "failures": 0}
