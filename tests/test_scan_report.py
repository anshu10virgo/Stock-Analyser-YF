"""Tests for the filters-first scan workbook and email report packaging."""

from __future__ import annotations

import io
import unittest
import zipfile
from datetime import datetime
from unittest.mock import patch

import pandas as pd

from services.scan_report import (
    MailConfiguration,
    build_chart_archives,
    build_messages,
    build_price_chart_png,
    build_workbook,
    parse_recipients,
    send_messages,
)


class ScanReportTests(unittest.TestCase):
    def setUp(self):
        self.scan_time = datetime(2026, 7, 27, 12, 30)
        self.settings = {
            "stock_market": "India — NSE",
            "market_data_source": "Git snapshot",
            "stock_count": 1500,
            "short_ma": 50,
            "long_ma": 200,
            "cross_age": 80,
            "min_long_ma_decline_duration": 60,
            "min_long_ma_decline": 10,
            "max_price_premium": 10,
            "include_impending_crosses": True,
            "impending_max_gap_pct": 3,
            "pre_cross_validation_sessions": 20,
            "adjusted_prices": False,
            "optional_filters": [
                {"key": "peg_ratio", "threshold": 1.0},
            ],
        }

    def test_recipients_are_validated_and_deduplicated(self):
        self.assertEqual(
            parse_recipients("one@example.com, two@example.com, one@example.com"),
            ("one@example.com", "two@example.com"),
        )
        with self.assertRaises(ValueError):
            parse_recipients("not-an-email")

    def test_workbook_starts_with_filters_sheet(self):
        workbook = build_workbook(
            self.settings,
            self.scan_time,
            pd.DataFrame([{"symbol": "POST.NS", "market_cap": 10_000_000}]),
            pd.DataFrame([{"symbol": "SOON.NS"}]),
        )
        excel = pd.ExcelFile(io.BytesIO(workbook))

        self.assertEqual(
            excel.sheet_names,
            ["Filters", "Post Golden Cross", "Impending Golden Cross"],
        )
        filters = pd.read_excel(io.BytesIO(workbook), sheet_name="Filters")
        self.assertIn("PEG Ratio", filters["Value"].astype(str).tolist())

    def test_chart_png_uses_maximum_supplied_history(self):
        index = pd.date_range("2020-01-01", periods=300, freq="B")
        values = pd.Series(range(100, 400), index=index, dtype=float)
        chart = pd.DataFrame(
            {
                "Close": values,
                "MA_SHORT": values.rolling(5).mean(),
                "MA_LONG": values.rolling(20).mean(),
            }
        )

        image = build_price_chart_png("TEST.NS", chart, index[200])

        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_chart_archives_split_and_preserve_files(self):
        images = [
            ("one.png", bytes(range(256)) * 4),
            ("two.png", bytes(reversed(range(256))) * 4),
        ]
        archives = build_chart_archives(images, max_bytes=400)

        self.assertEqual(len(archives), 2)
        filenames = []
        for payload in archives:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                filenames.extend(archive.namelist())
        self.assertEqual(filenames, ["one.png", "two.png"])

    @patch("services.scan_report.smtplib.SMTP_SSL")
    def test_messages_send_in_one_authenticated_session(self, smtp_ssl):
        messages = build_messages(
            ("one@example.com", "two@example.com"),
            "sender@example.com",
            self.scan_time,
            2,
            1,
            b"workbook",
            [b"archive-one", b"archive-two"],
        )
        send_messages(
            messages,
            MailConfiguration("sender@example.com", "secret"),
        )

        self.assertEqual(len(messages), 2)
        self.assertIn("Part 1 of 2", messages[0]["Subject"])
        self.assertEqual(len(list(messages[0].iter_attachments())), 2)
        self.assertEqual(len(list(messages[1].iter_attachments())), 1)
        smtp = smtp_ssl.return_value.__enter__.return_value
        smtp.login.assert_called_once_with("sender@example.com", "secret")
        self.assertEqual(smtp.send_message.call_count, 2)


if __name__ == "__main__":
    unittest.main()
