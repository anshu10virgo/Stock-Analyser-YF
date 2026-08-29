import unittest

import pandas as pd
import numpy as np

from models.backtest import HORIZON_SESSIONS
from models.scan_config import ScanConfig
from services.backtest_service import BacktestService


class BacktestServiceTests(unittest.TestCase):
    def test_horizons_use_expected_trading_sessions(self):
        self.assertEqual(HORIZON_SESSIONS, {"1W": 5, "2W": 10, "3W": 15, "1M": 21, "3M": 63, "6M": 126, "1Y": 252})

    def test_service_preserves_unadjusted_configuration(self):
        config = ScanConfig(50, 200, 80, 60, 10, 10, adjusted_prices=False)
        self.assertFalse(BacktestService(config).config.adjusted_prices)

    def test_pe_uses_latest_observation_on_or_before_signal(self):
        class Screener:
            @staticmethod
            def valuation_history(symbol):
                return pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]), "pe": [20.0, 0.0, 25.0]})

        service = BacktestService(ScanConfig(50, 200, 80, 60, 10, 10), Screener())
        pe, date = service._pe_at("TEST.NS", pd.Timestamp("2024-02-15"))
        self.assertEqual(pe, 20.0)
        self.assertEqual(date.date().isoformat(), "2024-01-01")

    def test_cross_age_uses_calendar_days(self):
        service = BacktestService(ScanConfig(50, 200, 80, 60, 10, 10))
        cross_date = pd.Timestamp("2024-01-01")
        self.assertTrue(service._within_cross_age(cross_date, pd.Timestamp("2024-03-21")))
        self.assertFalse(service._within_cross_age(cross_date, pd.Timestamp("2024-03-22")))

    def test_forward_returns_use_next_session_entry_and_available_close(self):
        history = pd.DataFrame({"Open": [90.0] * 7, "Close": [90.0, 100.0, 105.0, 106.0, 107.0, 108.0, 110.0]})
        returns = BacktestService._forward_returns(history, 1, 100.0)
        self.assertEqual(returns["1W"], 10.0)
        self.assertIsNone(returns["2W"])

    def test_one_signal_is_recorded_for_one_actual_cross(self):
        dates = pd.bdate_range("2020-01-01", periods=600)
        closes = np.r_[np.full(300, 100.0), np.linspace(101.0, 300.0, 300)]
        prices = pd.DataFrame({"Open": closes, "Close": closes}, index=dates)
        service = BacktestService(ScanConfig(50, 200, 80, 60, 10, 10))
        service._qualifies = lambda history: True
        run = service.replay_symbol("TEST.NS", prices)
        self.assertEqual(len(run.signals), 1)


if __name__ == "__main__":
    unittest.main()
