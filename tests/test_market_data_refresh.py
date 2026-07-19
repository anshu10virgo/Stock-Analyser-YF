"""Tests for fundamentals enrichment and snapshot refresh policies."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from scripts import refresh_market_data


class FakeClassificationProvider:
    def __init__(self, rows):
        self.rows = rows

    def classifications(self, symbols):
        return pd.DataFrame(self.rows, columns=refresh_market_data.CLASSIFICATION_COLUMNS)

    @staticmethod
    def metrics():
        return {"sector_requests": 1, "industry_requests": 1, "failures": 0}


class FakeQuoteProvider:
    def quotes(self):
        return {
            "TEST.NS": {
                "longName": "Test Company",
                "marketCap": 1_000,
                "regularMarketPrice": 100,
                "trailingPE": None,
                "epsTrailingTwelveMonths": 5,
            }
        }


class MarketDataRefreshTests(unittest.TestCase):
    def test_classification_refresh_preserves_existing_data_on_empty_response(self):
        with TemporaryDirectory() as directory, patch.object(
            refresh_market_data, "MARKET_ROOT", Path(directory)
        ):
            rows = [["TEST.NS", "Technology", "Software", "technology", "software"]]
            first = refresh_market_data.refresh_classifications(
                ["TEST.NS"], force=True, provider=FakeClassificationProvider(rows)
            )
            second = refresh_market_data.refresh_classifications(
                ["TEST.NS"], force=True, provider=FakeClassificationProvider([])
            )

        self.assertEqual(first.iloc[0]["industry"], "Software")
        self.assertEqual(second.iloc[0]["industry"], "Software")

    def test_build_fundamentals_calculates_pe_from_positive_eps(self):
        universe = pd.DataFrame(
            {"Symbol": ["TEST.NS"], "Company Name": ["Test Company"]}
        )
        classifications = pd.DataFrame(
            [["TEST.NS", "Technology", "Software", "technology", "software"]],
            columns=refresh_market_data.CLASSIFICATION_COLUMNS,
        )
        with patch.object(
            refresh_market_data,
            "YahooFinanceMarketCapProvider",
            return_value=FakeQuoteProvider(),
        ):
            result = refresh_market_data.build_fundamentals(
                universe, classifications
            ).iloc[0]

        self.assertEqual(result["pe"], 20)
        self.assertEqual(result["pe_source"], "price_divided_by_trailing_eps")
        self.assertEqual(result["industry"], "Software")

    def test_industry_valuation_uses_market_cap_implied_earnings(self):
        fundamentals = pd.DataFrame(
            {
                "industry": ["Software", "Software", "Software"],
                "pe": [10.0, 20.0, -5.0],
                "market_cap": [1_000.0, 100.0, 10_000.0],
            }
        )

        result = refresh_market_data.calculate_industry_valuations(
            fundamentals
        ).iloc[0]

        self.assertEqual(result["industry_peer_count"], 2)
        self.assertEqual(result["industry_median_pe"], 15)
        self.assertAlmostEqual(result["industry_weighted_pe"], 10.48)


if __name__ == "__main__":
    unittest.main()
