"""Regression tests for stock scanner qualification rules."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from core.data_loader import DataLoader
from core.fundamentals import Fundamentals
from core.golden_cross import GoldenCrossDetector
from core.indicators import Indicators
from core.scanner import StockScanner
from models.scan_config import ScanConfig
from providers.yahoo_finance import YahooFinanceHistoryProvider
from services.scan_service import ScanService


class StockScannerTests(unittest.TestCase):
    """Verify scanner price qualification rules."""

    @staticmethod
    def _scanner(**options) -> StockScanner:
        return StockScanner(50, 200, 60, 20, 20, 5, **options)

    @staticmethod
    def _transition_history(
        pre_increment=-1.0,
        post_increment=0.1,
        include_trough=True,
        constant_close=None,
    ):
        """Build history around a cross with controllable long-MA slopes."""
        dates = pd.bdate_range("2026-05-01", periods=31)
        pre_cross_long_ma = [120.0 + (pre_increment * index) for index in range(20)]
        cross_long_ma = pre_cross_long_ma[-1] + pre_increment
        post_cross_long_ma = [
            cross_long_ma + (post_increment * (index + 1))
            for index in range(10)
        ]
        long_ma = pre_cross_long_ma + [cross_long_ma] + post_cross_long_ma
        short_ma = [value - 1.0 for value in long_ma[:20]] + [
            value + 1.0 for value in long_ma[20:]
        ]
        lows = list(range(len(dates)))
        if include_trough:
            lows = [150.0] * len(dates)
            lows[10] = 100.0

        close = (
            [constant_close] * len(dates)
            if constant_close is not None
            else [value + 2.0 for value in long_ma]
        )

        history = pd.DataFrame(
            {
                "Close": close,
                "High": [value + 1.0 for value in close],
                "Low": lows,
                "MA_SHORT": short_ma,
                "MA_LONG": long_ma,
            },
            index=dates,
        )
        cross = {
            "valid": True,
            "cross_date": dates[20],
            "days_since_cross": 10,
        }
        return history, cross

    def _scan_history(self, history, cross, **options):
        with (
            patch.object(DataLoader, "download_batch", return_value=pd.DataFrame()),
            patch.object(DataLoader, "get_symbol_history", return_value=history),
            patch.object(Indicators, "add_moving_averages", return_value=history),
            patch.object(GoldenCrossDetector, "find_cross", return_value=cross),
        ):
            return self._scanner(**options).scan(["TEST.NS"])

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
            scanner = self._scanner()
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
            scanner = self._scanner()
            result = scanner.scan(["TEST.NS"])

        self.assertTrue(result["passed"].empty)
        self.assertEqual(result["failed"].loc[0, "stage"], "Price Validation")
        self.assertEqual(
            result["failed"].loc[0, "reason"],
            "Close price is below Short MA",
        )

    def test_rejects_golden_cross_invalidated_by_death_cross(self) -> None:
        """A later Death Cross must invalidate an earlier Golden Cross."""
        cross_date = pd.Timestamp("2026-07-07")
        history = pd.DataFrame(
            {
                "Close": [100.0, 101.0],
                "High": [101.0, 102.0],
                "Low": [99.0, 100.0],
                "MA_SHORT": [90.0, 99.0],
                "MA_LONG": [80.0, 100.0],
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
            scanner = self._scanner()
            result = scanner.scan(["TEST.NS"])

        self.assertTrue(result["passed"].empty)
        self.assertEqual(
            result["failed"].loc[0, "stage"],
            "Golden Cross Validation",
        )
        self.assertEqual(
            result["failed"].loc[0, "reason"],
            "Golden Cross has been invalidated by a Death Cross",
        )

    def test_rejects_when_no_trough_precedes_golden_cross(self) -> None:
        """A global trough count must not substitute for a pre-cross trough."""
        history, cross = self._transition_history(include_trough=False)
        result = self._scan_history(
            history,
            cross,
            require_pre_cross_trough=True,
        )

        self.assertTrue(result["passed"].empty)
        self.assertEqual(result["failed"].loc[0, "stage"], "Trough Validation")

    def test_rejects_when_long_ma_was_not_declining_before_cross(self) -> None:
        """The long MA must decline over the configured pre-cross window."""
        history, cross = self._transition_history(pre_increment=1.0)
        result = self._scan_history(
            history,
            cross,
            require_pre_cross_decline=True,
        )

        self.assertTrue(result["passed"].empty)
        self.assertEqual(result["failed"].loc[0, "stage"], "Slope Validation")
        self.assertEqual(
            result["failed"].loc[0, "reason"],
            "Long MA was not declining before Golden Cross",
        )

    def test_rejects_when_long_ma_is_not_increasing_after_cross(self) -> None:
        """The long MA must increase after the Golden Cross."""
        history, cross = self._transition_history(
            post_increment=-0.1,
            constant_close=200.0,
        )
        result = self._scan_history(
            history,
            cross,
            require_post_cross_increase=True,
        )

        self.assertTrue(result["passed"].empty)
        self.assertEqual(result["failed"].loc[0, "stage"], "Slope Validation")
        self.assertEqual(
            result["failed"].loc[0, "reason"],
            "Long MA is not increasing after Golden Cross",
        )

    def test_accepts_valid_pre_cross_trough_and_slope_transition(self) -> None:
        """A valid trough and decline-to-rise MA transition must qualify."""
        history, cross = self._transition_history()
        fundamentals = {
            "company_name": "Test Company",
            "market_cap": None,
            "pe": None,
            "eps": None,
            "sector": None,
            "industry": None,
        }

        with patch.object(Fundamentals, "get_fundamentals", return_value=fundamentals):
            result = self._scan_history(
                history,
                cross,
                require_pre_cross_trough=True,
                require_pre_cross_decline=True,
                require_post_cross_sessions=True,
                require_post_cross_increase=True,
            )

        self.assertEqual(len(result["passed"]), 1)

    def test_optional_checks_do_not_reject_when_not_selected(self) -> None:
        """Optional trough and slope checks must not filter the base scan."""
        history, cross = self._transition_history(
            include_trough=False,
            pre_increment=1.0,
            post_increment=-0.1,
            constant_close=142.0,
        )
        fundamentals = {
            "company_name": "Test Company",
            "market_cap": None,
            "pe": None,
            "eps": None,
            "sector": None,
            "industry": None,
        }

        with patch.object(Fundamentals, "get_fundamentals", return_value=fundamentals):
            result = self._scan_history(history, cross)

        self.assertEqual(len(result["passed"]), 1)

    def test_invalid_scan_configuration_fails_fast(self) -> None:
        """Impossible MA settings must be rejected before a data download."""
        config = ScanConfig(
            short_ma=200,
            long_ma=50,
            max_cross_age=60,
            pre_cross_days=20,
            slope_lookback=20,
            max_distance=5,
        )

        with self.assertRaises(ValueError):
            ScanService(config)

    def test_batch_download_failure_is_reported_for_every_symbol(self) -> None:
        """Provider outages must become visible structured failures."""
        config = ScanConfig(50, 200, 60, 20, 20, 5)
        with patch.object(DataLoader, "download_batch", side_effect=RuntimeError):
            result = ScanService(config).scan(["ONE.NS", "TWO.NS"])

        frames = result.as_dataframes()
        self.assertTrue(frames["passed"].empty)
        self.assertEqual(len(frames["failed"]), 2)
        self.assertTrue((frames["failed"]["stage"] == "Market Data").all())

    def test_history_provider_reuses_cached_batch_data(self) -> None:
        """Repeated scans should not re-download an unchanged price batch."""
        provider = YahooFinanceHistoryProvider()
        downloaded = pd.DataFrame({"Close": [100.0]})

        with patch("providers.yahoo_finance.yf.download", return_value=downloaded) as download:
            first = provider.download_batch(["TEST.NS"])
            second = provider.download_batch(["TEST.NS"])

        self.assertEqual(download.call_count, 1)
        self.assertFalse(first is second)
        self.assertEqual(provider.metrics()["cache_hits"], 1)
