import unittest

import pandas as pd

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


if __name__ == "__main__":
    unittest.main()
