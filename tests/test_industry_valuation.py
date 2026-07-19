"""Tests for NSE-only industry P/E benchmark calculation."""

import unittest
from unittest.mock import patch

from providers.yahoo_finance import YahooFinanceIndustryProvider
from services.industry_valuation import IndustryValuationService


class FakeIndustryProvider:
    def __init__(self, quotes):
        self.quotes = quotes
        self.calls = 0

    def industry_quotes(self, industry):
        self.calls += 1
        return self.quotes


class IndustryValuationTests(unittest.TestCase):
    @patch(
        "providers.yahoo_finance.yf.screen",
        return_value={"quotes": [{"symbol": "TEST.NS"}], "total": 1},
    )
    def test_normalizes_grouped_industry_name_for_yahoo_screener(self, screen):
        quotes = YahooFinanceIndustryProvider.industry_quotes(
            "Software - Application"
        )

        self.assertEqual(quotes, [{"symbol": "TEST.NS"}])
        screen.assert_called_once()

    def test_calculates_weighted_and_median_pe_from_nse_peers(self):
        """BSE duplicates, loss makers, and missing values must not skew P/E."""
        provider = FakeIndustryProvider(
            [
                {"symbol": "LARGE.NS", "marketCap": 1_000, "trailingPE": 10},
                {"symbol": "KPEL.NS", "marketCap": 100, "trailingPE": 20},
                {"symbol": "LARGE.BO", "marketCap": 1_000, "trailingPE": 10},
                {"symbol": "LOSS.NS", "marketCap": 500, "trailingPE": None},
                {"symbol": "MISSING.NS", "marketCap": None, "trailingPE": 15},
            ]
        )
        service = IndustryValuationService(provider)

        result = service.valuation_for("Engineering & Construction")

        self.assertEqual(result["industry_peer_count"], 2)
        self.assertEqual(result["industry_median_pe"], 15)
        self.assertAlmostEqual(result["industry_weighted_pe"], 10.48)

    def test_caches_industry_result_for_the_scan(self):
        """Repeated qualifying stocks in one industry reuse the peer dataset."""
        provider = FakeIndustryProvider(
            [{"symbol": "TEST.NS", "marketCap": 100, "trailingPE": 10}]
        )
        service = IndustryValuationService(provider)

        service.valuation_for("Test Industry")
        service.valuation_for("Test Industry")

        self.assertEqual(provider.calls, 1)
        self.assertEqual(service.metrics()["cache_hits"], 1)

    def test_starts_each_scan_with_a_fresh_peer_snapshot(self):
        """A new scan must not reuse a prior scan's live industry benchmark."""
        provider = FakeIndustryProvider(
            [{"symbol": "TEST.NS", "marketCap": 100, "trailingPE": 10}]
        )
        service = IndustryValuationService(provider)

        service.valuation_for("Test Industry")
        service.begin_scan()
        service.valuation_for("Test Industry")

        self.assertEqual(provider.calls, 2)


if __name__ == "__main__":
    unittest.main()
