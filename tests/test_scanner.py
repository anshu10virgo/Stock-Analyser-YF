"""Regression tests for the mandatory reversal-rule scanner."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from core.data_loader import DataLoader
from core.golden_cross import GoldenCrossDetector
from core.indicators import Indicators
from core.scoring import ScoringEngine
from models.scan_config import ScanConfig
from providers.yahoo_finance import YahooFinanceHistoryProvider
from scripts.refresh_stock_universe import build_candidates, rank_by_market_cap
from services.scan_service import ScanService
from services.stock_universe import StockUniverse


class StaticFundamentals:
    @staticmethod
    def get_fundamentals(symbol):
        return {
            "company_name": "Test Company",
            "market_cap": None,
            "pe": None,
            "eps": None,
            "sector": None,
            "industry": None,
        }


class StaticIndustryValuation:
    @staticmethod
    def valuation_for(industry):
        return {
            "industry_weighted_pe": None,
            "industry_median_pe": None,
            "industry_peer_count": 0,
        }


class StockScannerTests(unittest.TestCase):
    """Verify Post-Cross, Impending-Cross, and shared scanner rules."""

    @staticmethod
    def _config(**overrides):
        settings = {
            "short_ma": 50,
            "long_ma": 200,
            "max_cross_age": 80,
            "min_long_ma_decline_duration": 5,
            "min_long_ma_decline": 10,
            "max_price_premium": 10,
        }
        settings.update(overrides)
        return ScanConfig(**settings)

    @staticmethod
    def _history():
        """Return a history that passes every mandatory rule by default."""
        dates = pd.bdate_range("2025-06-01", periods=280)
        long_ma = (
            [100.0] * 260
            + [100 - (0.55 * index) for index in range(14)]
            + [89.0, 89.2, 89.4, 89.6, 89.8, 90.0]
        )
        short_ma = [95.0] * 275 + [87.0, 88.0, 89.0, 91.0, 92.0]
        close = [101.0] * 279 + [95.0]
        return pd.DataFrame(
            {
                "Close": close,
                "High": [value + 1 for value in close],
                "Low": [value - 1 for value in close],
                "MA_SHORT": short_ma,
                "MA_LONG": long_ma,
            },
            index=dates,
        )

    def _scan(self, history, cross_date=None, result_callback=None, **config_overrides):
        cross_date = cross_date or history.index[-15]
        cross = {
            "valid": True,
            "cross_date": cross_date,
            "days_since_cross": 15,
        }
        with (
            patch.object(DataLoader, "download_batch", return_value=pd.DataFrame()),
            patch.object(DataLoader, "get_symbol_history", return_value=history),
            patch.object(Indicators, "add_moving_averages", return_value=history),
            patch.object(GoldenCrossDetector, "find_cross", return_value=cross),
        ):
            return ScanService(
                self._config(**config_overrides),
                fundamentals_provider=StaticFundamentals,
                industry_valuation_service=StaticIndustryValuation(),
            ).scan(["TEST.NS"], result_callback=result_callback).as_dataframes()

    @staticmethod
    def _impending_history():
        history = StockScannerTests._history()
        recent = history.index[-21:]
        history.loc[recent, "MA_SHORT"] = history.loc[recent, "MA_LONG"] - 2
        history.loc[history.index[-5]:, "MA_SHORT"] = (
            history.loc[history.index[-5]:, "MA_LONG"]
            - [1.5, 1.2, 0.9, 0.5, 0.2]
        )
        return history

    def test_result_callback_receives_accumulated_scan_outcomes(self):
        updates = []

        self._scan(
            self._history(),
            result_callback=lambda current, total, run: updates.append(
                (current, total, len(run.passed), len(run.failed))
            ),
        )

        self.assertEqual(updates, [(1, 1, 1, 0)])

    def test_accepts_stock_matching_all_new_mandatory_rules(self):
        """The new rule set accepts a fresh reversal near the Long MA."""
        result = self._scan(self._history())

        self.assertEqual(len(result["passed"]), 1)
        record = result["passed"].iloc[0]
        self.assertTrue(record["short_ma_rising"])
        self.assertEqual(record["long_ma_peak_age"], 19)
        self.assertAlmostEqual(record["long_ma_decline_percent"], 11.0)
        self.assertAlmostEqual(record["price_above_long_ma_percent"], 5.56)

    def test_rejects_short_ma_that_is_not_rising(self):
        history = self._history()
        history.loc[history.index[-5]:, "MA_SHORT"] = [92.0, 91.0, 90.0, 89.0, 88.0]

        result = self._scan(history)

        self.assertEqual(result["failed"].loc[0, "stage"], "Short MA Validation")
        self.assertEqual(result["failed"].loc[0, "reason"], "Short MA 5-session slope is not positive")

    def test_accepts_positive_short_ma_slope_when_last_day_is_lower(self):
        history = self._history()
        history.loc[history.index[-5]:, "MA_SHORT"] = [87.0, 88.0, 89.0, 93.0, 92.0]

        result = self._scan(history)

        self.assertEqual(len(result["passed"]), 1)
        self.assertGreater(result["passed"].loc[0, "short_ma_slope"], 0)

    def test_rejects_short_ma_equal_to_long_ma(self):
        history = self._history()
        history.iloc[-2, history.columns.get_loc("MA_SHORT")] = 88.0
        history.iloc[-1, history.columns.get_loc("MA_SHORT")] = history.iloc[-1]["MA_LONG"]

        result = self._scan(history)

        self.assertEqual(result["failed"].loc[0, "reason"], "Short MA is not above Long MA")

    def test_rejects_long_ma_decline_shorter_than_configured_duration(self):
        history = self._history()
        history.loc[history.index[-32]:, "MA_LONG"] = (
            [100 - (0.4 * index) for index in range(26)]
            + [88.0, 88.2, 88.4, 88.6, 88.8, 89.0]
        )
        history.iloc[-1, history.columns.get_loc("MA_SHORT")] = 92.0

        result = self._scan(history, min_long_ma_decline_duration=30)

        self.assertEqual(
            result["failed"].loc[0, "reason"],
            "Long MA decline from 52-week high to trough is shorter than configured minimum duration",
        )

    def test_rejects_long_ma_decline_below_minimum(self):
        history = self._history()
        history.loc[history.index[-6]:, "MA_LONG"] = [95.0, 95.2, 95.4, 95.6, 95.8, 96.0]
        history.iloc[-1, history.columns.get_loc("MA_SHORT")] = 97.0

        result = self._scan(history)

        self.assertEqual(result["failed"].loc[0, "reason"], "Long MA decline from 52-week high to trough is below configured minimum")

    def test_rejects_long_ma_without_a_positive_post_trough_five_day_slope(self):
        history = self._history()
        history.loc[history.index[-5]:, "MA_LONG"] = 90.0

        result = self._scan(history)

        self.assertEqual(result["failed"].loc[0, "reason"], "Post-trough 5-session Long MA slope is not positive")

    def test_rejects_close_at_or_below_long_ma(self):
        history = self._history()
        history.iloc[-1, history.columns.get_loc("Close")] = history.iloc[-1]["MA_LONG"]

        result = self._scan(history)

        self.assertEqual(result["failed"].loc[0, "reason"], "Close price is not above Long MA")

    def test_rejects_close_more_than_maximum_premium_above_long_ma(self):
        history = self._history()
        history.iloc[-1, history.columns.get_loc("Close")] = 100.0

        result = self._scan(history)

        self.assertEqual(result["failed"].loc[0, "reason"], "Close price is too far above Long MA")

    def test_optional_post_cross_session_check_is_enforced_only_when_selected(self):
        history = self._history()
        result = self._scan(
            history,
            cross_date=history.index[-5],
            require_post_cross_sessions=True,
        )

        self.assertEqual(result["failed"].loc[0, "stage"], "Post-Cross Validation")
        self.assertEqual(result["failed"].loc[0, "check_type"], "optional")

    def test_accepts_an_impending_cross_into_a_separate_result_group(self):
        result = self._scan(
            self._impending_history(),
            include_impending_crosses=True,
        )

        self.assertTrue(result["passed"].empty)
        self.assertEqual(len(result["impending"]), 1)
        record = result["impending"].iloc[0]
        self.assertEqual(record["strategy"], "Impending Golden Cross")
        self.assertLessEqual(record["impending_gap_percent"], 3)
        self.assertGreater(record["short_ma_slope"], record["long_ma_slope"])
        self.assertTrue(pd.isna(record["cross_date"]))

    def test_impending_cross_respects_the_configured_gap(self):
        result = self._scan(
            self._impending_history(),
            include_impending_crosses=True,
            impending_max_gap_pct=0.1,
        )

        self.assertEqual(
            result["failed"].loc[0, "reason"],
            "Short MA is farther below Long MA than the configured maximum gap",
        )

    def test_impending_cross_requires_short_ma_to_rise_faster(self):
        history = self._impending_history()
        history.loc[history.index[-5]:, "MA_SHORT"] = (
            history.loc[history.index[-5]:, "MA_LONG"] - 0.5
        )

        result = self._scan(history, include_impending_crosses=True)

        self.assertEqual(
            result["failed"].loc[0, "reason"],
            "Short MA 5-session slope is not greater than Long MA 5-session slope",
        )

    def test_impending_cross_requires_a_fresh_pre_cross_window(self):
        history = self._impending_history()
        history.loc[history.index[-10], "MA_SHORT"] = history.loc[
            history.index[-10], "MA_LONG"
        ]

        result = self._scan(history, include_impending_crosses=True)

        self.assertEqual(
            result["failed"].loc[0, "reason"],
            "Short MA was not strictly below Long MA throughout the configured pre-cross validation period",
        )

    def test_impending_cross_allows_a_flat_latest_long_ma(self):
        history = self._impending_history()
        history.loc[history.index[-5]:, "MA_LONG"] = 90.0
        history.loc[history.index[-5]:, "MA_SHORT"] = [87.0, 87.5, 88.0, 89.0, 89.8]

        result = self._scan(history, include_impending_crosses=True)

        self.assertEqual(len(result["impending"]), 1)
        self.assertEqual(result["impending"].loc[0, "long_ma_slope"], 0)

    def test_invalid_scan_configuration_fails_fast(self):
        """Impossible MA settings must be rejected before a data download."""
        with self.assertRaises(ValueError):
            ScanService(self._config(short_ma=200, long_ma=50))

    def test_batch_download_failure_is_reported_for_every_symbol(self):
        """Provider outages must become visible structured failures."""
        with patch.object(DataLoader, "download_batch", side_effect=RuntimeError):
            result = ScanService(self._config()).scan(["ONE.NS", "TWO.NS"])

        frames = result.as_dataframes()
        self.assertTrue(frames["passed"].empty)
        self.assertEqual(len(frames["failed"]), 2)
        self.assertTrue((frames["failed"]["stage"] == "Market Data").all())

    def test_history_provider_reuses_cached_batch_data(self):
        """Repeated scans should not re-download an unchanged price batch."""
        provider = YahooFinanceHistoryProvider()
        downloaded = pd.DataFrame({"Close": [100.0]})

        with patch("providers.yahoo_finance.yf.download", return_value=downloaded) as download:
            provider.download_batch(["TEST.NS"])
            provider.download_batch(["TEST.NS"])

        self.assertEqual(download.call_count, 1)
        self.assertEqual(provider.metrics()["cache_hits"], 1)

    def test_score_breakdown_matches_the_total_score(self):
        breakdown = ScoringEngine.score_breakdown(
            days_since_cross=5,
            slope_label="STRONG_POSITIVE",
            distance=1,
            fundamentals={"pe": 15, "eps": 1, "market_cap": 250_000_000_000},
        )

        self.assertEqual(sum(breakdown.values()), ScoringEngine.MAX_SCORE)

    def test_manifest_selects_the_active_validated_universe(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            validated = root / "validated"
            validated.mkdir()
            active_file = validated / "yahoo_nse_2026-07-18.csv"
            active_file.write_text("Symbol\nTEST.NS\n", encoding="utf-8")
            (root / "manifest.json").write_text(
                json.dumps({"active_universe": "validated/yahoo_nse_2026-07-18.csv"}),
                encoding="utf-8",
            )

            universe = StockUniverse(root)
            self.assertEqual(universe.active_file(), active_file.resolve())

    def test_missing_universe_manifest_has_no_legacy_fallback(self):
        with TemporaryDirectory() as temporary_directory:
            with self.assertRaises(FileNotFoundError):
                StockUniverse(Path(temporary_directory)).active_file()

    def test_refresh_parser_normalizes_nse_whitespace_headers(self):
        raw_source = (
            b"SYMBOL,NAME OF COMPANY, SERIES, ISIN NUMBER\n"
            b"TESTCO,Test Company,EQ,INE000A01001\n"
        )

        candidates = build_candidates(raw_source, "EQ")

        self.assertEqual(candidates.loc[0, "Symbol"], "TESTCO.NS")

    def test_market_cap_ranking_orders_the_universe_for_top_n_scans(self):
        validated = pd.DataFrame(
            {
                "Symbol": ["SMALL.NS", "UNKNOWN.NS", "LARGE.NS"],
                "Company Name": ["Small", "Unknown", "Large"],
            }
        )

        ranked = rank_by_market_cap(
            validated,
            {"SMALL.NS": 50_000_000_000, "LARGE.NS": 500_000_000_000},
        )

        self.assertEqual(ranked["Symbol"].tolist(), ["LARGE.NS", "SMALL.NS", "UNKNOWN.NS"])
        self.assertEqual(ranked["Market Cap Rank"].tolist()[:2], [1, 2])
        self.assertTrue(pd.isna(ranked["Market Cap Rank"].iloc[2]))

    def test_symbol_loader_uses_stored_market_cap_rank(self):
        with TemporaryDirectory() as temporary_directory:
            universe_file = Path(temporary_directory) / "universe.csv"
            universe_file.write_text(
                "Symbol,Market Cap Rank\nSMALL.NS,2\nLARGE.NS,1\nUNKNOWN.NS,\n",
                encoding="utf-8",
            )

            symbols = DataLoader.load_symbols(universe_file)

        self.assertEqual(symbols, ["LARGE.NS", "SMALL.NS", "UNKNOWN.NS"])


if __name__ == "__main__":
    unittest.main()
