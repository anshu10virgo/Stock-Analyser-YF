"""Regression tests for stock scanner qualification rules."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from core.data_loader import DataLoader
from core.golden_cross import GoldenCrossDetector
from core.indicators import Indicators
from core.scanner import StockScanner


class StockScannerTests(unittest.TestCase):
    """Verify scanner price qualification rules."""

    def test_rejects_close_below_golden_cross_close(self) -> None:
        """Latest close below the Golden Cross close must not qualify."""
        cross_date = pd.Timestamp("2026-07-07")
        history = pd.DataFrame(
            {
                "Close": [100.0, 95.0],
                "High": [101.0, 96.0],
                "Low": [99.0, 94.0],
                "MA_SHORT": [90.0, 90.0],
                "MA_LONG": [80.0, 80.0],
            },
            index=[cross_date, pd.Timestamp("2026-07-08")],
        )
        cross = {
            "valid": True,
            "cross_date": cross_date,
            "days_since_cross": 1,
        }

        with (
            patch.object(DataLoader, "download_batch", return_value=pd.DataFrame()),
            patch.object(DataLoader, "get_symbol_history", return_value=history),
            patch.object(Indicators, "add_moving_averages", return_value=history),
            patch.object(GoldenCrossDetector, "find_cross", return_value=cross),
        ):
            scanner = StockScanner(50, 200, 60, 20, 120, 2, 20, 5)
            result = scanner.scan(["TEST.NS"])

        self.assertTrue(result["passed"].empty)
        self.assertEqual(result["failed"].loc[0, "stage"], "Price Validation")
        self.assertEqual(
            result["failed"].loc[0, "reason"],
            "Close price is below Golden Cross close",
        )

    def test_rejects_close_below_short_ma(self) -> None:
        """Latest close must be at or above the current short MA."""
        cross_date = pd.Timestamp("2026-07-07")
        history = pd.DataFrame(
            {
                "Close": [100.0, 101.0],
                "High": [101.0, 102.0],
                "Low": [99.0, 100.0],
                "MA_SHORT": [90.0, 102.0],
                "MA_LONG": [80.0, 80.0],
            },
            index=[cross_date, pd.Timestamp("2026-07-08")],
        )
        cross = {
            "valid": True,
            "cross_date": cross_date,
            "days_since_cross": 1,
        }

        with (
            patch.object(DataLoader, "download_batch", return_value=pd.DataFrame()),
            patch.object(DataLoader, "get_symbol_history", return_value=history),
            patch.object(Indicators, "add_moving_averages", return_value=history),
            patch.object(GoldenCrossDetector, "find_cross", return_value=cross),
        ):
            scanner = StockScanner(50, 200, 60, 20, 120, 2, 20, 5)
            result = scanner.scan(["TEST.NS"])

        self.assertTrue(result["passed"].empty)
        self.assertEqual(result["failed"].loc[0, "stage"], "Price Validation")
        self.assertEqual(
            result["failed"].loc[0, "reason"],
            "Close price is below Short MA",
        )
