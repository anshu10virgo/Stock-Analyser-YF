"""Focused characterization tests for Sprint F domain extraction."""

from __future__ import annotations

import unittest
from datetime import datetime

import pandas as pd

from models.backtest import BacktestSignal as LegacyBacktestSignal
from stock_analyser.domain.backtesting import (
    BacktestSignal,
    forward_returns,
    summarize_returns,
    valuation_at,
    within_cross_age,
)
from stock_analyser.domain.reporting import (
    ReportContext,
    ReportCounts,
    attachment_batches,
    chart_snapshot_spec,
    filter_records,
    message_content,
    parse_recipients,
    workbook_frames,
)


class BacktestingDomainTests(unittest.TestCase):
    def test_legacy_model_is_canonical_domain_model(self):
        self.assertIs(LegacyBacktestSignal, BacktestSignal)

    def test_forward_returns_and_cross_age_preserve_existing_rules(self):
        history = pd.DataFrame(
            {"Close": [90.0, 100.0, 105.0, 106.0, 107.0, 108.0, 110.0]}
        )
        returns = forward_returns(history, 1, 100.0)
        self.assertEqual(returns["1W"], 10.0)
        self.assertIsNone(returns["2W"])
        self.assertTrue(
            within_cross_age(
                pd.Timestamp("2024-01-01"), pd.Timestamp("2024-03-21"), 80
            )
        )

    def test_valuation_and_aggregate_metrics_use_available_observations(self):
        history = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-02-01"]),
                "pe": [20.0, 0.0],
            }
        )
        pe, date = valuation_at(history, pd.Timestamp("2024-02-15"))
        self.assertEqual(pe, 20.0)
        self.assertEqual(date.date().isoformat(), "2024-01-01")
        summary = summarize_returns(pd.Series([10.0, None, -2.0]), signal_count=3)
        self.assertEqual(summary.observed_count, 2)
        self.assertEqual(summary.average_return, 4.0)
        self.assertEqual(summary.median_return, 4.0)


class ReportingDomainTests(unittest.TestCase):
    def test_recipients_are_validated_and_deduplicated(self):
        self.assertEqual(
            parse_recipients("one@example.com, two@example.com, one@example.com"),
            ("one@example.com", "two@example.com"),
        )

    def test_filters_remain_first_and_market_cap_is_converted_to_crore(self):
        scan_time = datetime(2026, 10, 19, 12, 30)
        frames = workbook_frames(
            {"market_data_source": "Git snapshot", "optional_filters": ()},
            scan_time,
            pd.DataFrame([{"symbol": "A.NS", "market_cap": 10_000_000}]),
            pd.DataFrame(),
            market_data_source_label="Cloud snapshot",
        )
        self.assertEqual(
            list(frames),
            ["Filters", "Post Golden Cross", "Impending Golden Cross"],
        )
        self.assertEqual(frames["Post Golden Cross"].iloc[0]["Market Cap (₹ Cr)"], 1)
        records = filter_records(
            {"market_data_source": "Git snapshot"},
            scan_time,
            market_data_source_label="Cloud snapshot",
        )
        self.assertIn(
            {"Setting": "Market-data source", "Value": "Cloud snapshot"}, records
        )

    def test_chart_batch_and_message_decisions_are_transport_independent(self):
        specification = chart_snapshot_spec("TEST.NS", pd.Timestamp("2026-01-01"))
        self.assertIn("Maximum available price history", specification.title)
        batches = attachment_batches(
            [b"one", b"two", b"three"],
            lambda items: sum(len(item) for item in items),
            max_bytes=6,
        )
        self.assertEqual(batches, [[b"one", b"two"], [b"three"]])
        content = message_content(
            ReportContext(
                datetime(2026, 10, 19, 12, 30),
                ReportCounts(post_cross=2, impending=1),
            ),
            part_number=1,
            part_count=2,
        )
        self.assertIn("Part 1 of 2", content.subject)
        self.assertIn("Post Golden Cross stocks: 2", content.body)


if __name__ == "__main__":
    unittest.main()
