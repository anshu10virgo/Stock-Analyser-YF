"""Market-cap refresh fallback behavior."""

import unittest
from unittest.mock import patch

from providers.yahoo_finance import YahooFinanceMarketCapProvider
from yfinance.exceptions import YFRateLimitError


class MarketCapFallbackTests(unittest.TestCase):
    def test_rate_limit_aborts_before_requesting_later_batches(self):
        provider = YahooFinanceMarketCapProvider()
        provider._quotes = {}
        with patch.object(provider, "_direct_market_cap", side_effect=YFRateLimitError()) as direct:
            with self.assertRaises(YFRateLimitError):
                provider.market_caps([f"{number}.NS" for number in range(100)])
        self.assertLessEqual(direct.call_count, 8)

    def test_direct_rate_limit_is_not_treated_as_missing_cap(self):
        with patch(
            "stock_analyser.infrastructure.yahoo.providers.yf.Ticker",
            side_effect=YFRateLimitError(),
        ):
            with self.assertRaises(YFRateLimitError):
                YahooFinanceMarketCapProvider._direct_market_cap("A.NS")

    def test_populated_screener_avoids_direct_requests(self):
        provider = YahooFinanceMarketCapProvider()
        provider._quotes = {"A.NS": {"marketCap": 100}}
        with patch.object(provider, "_direct_market_cap") as direct:
            self.assertEqual(provider.market_caps(["A.NS"]), {"A.NS": 100})
        direct.assert_not_called()

    def test_empty_screener_fetches_unique_requested_symbols(self):
        provider = YahooFinanceMarketCapProvider()
        provider._quotes = {}
        with patch.object(provider, "_direct_market_cap", side_effect=lambda s: (s, 100)) as direct:
            self.assertEqual(provider.market_caps(["A.NS", "A.NS", "B.NS"]),
                             {"A.NS": 100, "B.NS": 100})
        self.assertEqual(direct.call_count, 2)
        self.assertEqual(provider.metrics()["direct_requests"], 2)

    def test_invalid_direct_values_remain_unranked(self):
        for value in [None, float("nan"), float("inf"), -1, 0]:
            with self.subTest(value=value), patch(
                "stock_analyser.infrastructure.yahoo.providers.yf.Ticker"
            ) as ticker:
                ticker.return_value.fast_info.market_cap = value
                self.assertEqual(YahooFinanceMarketCapProvider._direct_market_cap("A.NS"),
                                 ("A.NS", None))

    def test_no_symbols_preserves_existing_screener_contract(self):
        provider = YahooFinanceMarketCapProvider()
        provider._quotes = {}
        with patch.object(provider, "_direct_market_cap") as direct:
            self.assertEqual(provider.market_caps(), {})
        direct.assert_not_called()
