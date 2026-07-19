"""Tests for locally derived scan insights and immutable UI defaults."""

import unittest

import pandas as pd

from ui.scan_insights import derive_scan_insights
from ui.sidebar import DEFAULT_SCAN_SETTINGS, default_scan_settings


class ScanInsightTests(unittest.TestCase):
    def test_derives_insights_from_scan_fields_only(self):
        passed = pd.DataFrame(
            [
                {
                    "symbol": "ONE.NS",
                    "score": 70,
                    "days_since_cross": 20,
                    "pe": 10,
                    "industry_median_pe": 20,
                    "long_ma_recovery_slope": 0.2,
                },
                {
                    "symbol": "TWO.NS",
                    "score": 80,
                    "days_since_cross": 5,
                    "pe": 18,
                    "industry_median_pe": 22,
                    "long_ma_recovery_slope": 0.5,
                },
            ]
        )
        failed = pd.DataFrame(
            {"stage": ["Price Validation", "Price Validation", "Market Data"]}
        )

        insights = derive_scan_insights(passed, failed)

        self.assertEqual(insights["Highest score"], "TWO.NS · 80")
        self.assertEqual(insights["Newest Golden Cross"], "TWO.NS · 5 days")
        self.assertIn("Price Validation", insights["Most common rejection"])

    def test_default_settings_are_returned_as_an_independent_copy(self):
        settings = default_scan_settings()
        settings["short_ma"] = 10

        self.assertEqual(DEFAULT_SCAN_SETTINGS["short_ma"], 50)


if __name__ == "__main__":
    unittest.main()
