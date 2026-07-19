"""Tests for committed market-data reads and deterministic refresh replay."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pandas as pd

from providers.repository_data import (
    RepositoryFundamentalsProvider,
    RepositoryHistoryProvider,
)
from scripts import refresh_market_data


def price_rows(symbol="TEST.NS"):
    return pd.DataFrame(
        {
            "Date": ["2026-07-16", "2026-07-17"],
            "Symbol": [symbol, symbol],
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Adj Close": [101.0, 102.0],
            "Volume": [1000, 1200],
        }
    )


class RepositoryMarketDataTests(unittest.TestCase):
    def _snapshot(self, root: Path):
        prices = root / "prices"
        prices.mkdir(parents=True)
        price_file = prices / "2026.csv"
        price_rows().to_csv(price_file, index=False)
        (root / "manifest.json").write_text(
            json.dumps({"price_files": [{"path": "prices/2026.csv"}]}),
            encoding="utf-8",
        )

    def test_existing_snapshot_does_not_call_yahoo_fallback(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self._snapshot(root)
            fallback = Mock()
            provider = RepositoryHistoryProvider(root, fallback=fallback)

            batch = provider.download_batch(["TEST.NS"], years=1)
            history = provider.get_symbol_history(batch, "TEST.NS")

        self.assertEqual(len(history), 2)
        fallback.download_batch.assert_not_called()
        self.assertEqual(provider.market_data_metrics()["snapshot_hits"], 1)

    def test_missing_snapshot_uses_yahoo_fallback(self):
        fallback = Mock()
        fallback.download_batch.return_value = pd.DataFrame({"Close": [100.0]})
        with TemporaryDirectory() as directory:
            provider = RepositoryHistoryProvider(Path(directory), fallback=fallback)
            provider.download_batch(["MISSING.NS"], years=1)

        fallback.download_batch.assert_called_once()

    def test_blank_stored_fundamentals_do_not_trigger_fallback(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fundamentals = root / "fundamentals"
            fundamentals.mkdir()
            pd.DataFrame(
                [{"symbol": "TEST.NS", "company_name": "Test", "industry": None}]
            ).to_csv(fundamentals / "fundamentals.csv", index=False)
            fallback = Mock()
            provider = RepositoryFundamentalsProvider(root, fallback=fallback)

            result = provider.get_fundamentals("TEST.NS")

        self.assertIsNone(result["industry"])
        fallback.get_fundamentals.assert_not_called()

    def test_replay_builds_snapshot_without_yahoo(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            replay_file = root / "replay.csv"
            price_rows().to_csv(replay_file, index=False)
            universe_frame = pd.DataFrame(
                {"Symbol": ["TEST.NS"], "Company Name": ["Test Company"]}
            )
            universe = Mock()
            universe.metadata.return_value = {"sha256": "universe-hash"}
            fundamentals = pd.DataFrame(
                [
                    {
                        "symbol": "TEST.NS",
                        "company_name": "Test Company",
                        "market_cap": 1000,
                        "pe": 10,
                        "forward_pe": 9,
                        "eps": 5,
                        "sector": None,
                        "industry": None,
                        "revenue_growth": None,
                        "earnings_growth": None,
                    }
                ]
            )
            with (
                patch.object(refresh_market_data, "MARKET_ROOT", root / "market_data"),
                patch.object(
                    refresh_market_data,
                    "active_universe",
                    return_value=(universe, universe_frame, ["TEST.NS"]),
                ),
                patch.object(
                    refresh_market_data,
                    "build_fundamentals",
                    return_value=fundamentals,
                ),
            ):
                manifest = refresh_market_data.refresh(
                    "incremental", replay_file=replay_file
                )

        self.assertEqual(manifest["last_trading_date"], "2026-07-17")
        self.assertEqual(manifest["symbol_count"], 1)

    def test_incremental_discards_stale_rows_but_keeps_new_symbol_backfill(self):
        existing = price_rows()
        incoming = pd.concat(
            [
                price_rows().iloc[[1]],
                price_rows("NEW.NS").iloc[[0]],
            ],
            ignore_index=True,
        )
        existing["Date"] = pd.to_datetime(existing["Date"])
        incoming["Date"] = pd.to_datetime(incoming["Date"])

        retained = refresh_market_data.retain_new_incremental_rows(
            incoming, existing
        )

        self.assertEqual(retained["Symbol"].tolist(), ["NEW.NS"])
        self.assertEqual(retained["Date"].dt.strftime("%Y-%m-%d").tolist(), ["2026-07-16"])


if __name__ == "__main__":
    unittest.main()
