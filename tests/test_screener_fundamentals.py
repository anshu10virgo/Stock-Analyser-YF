"""Tests for Screener parsing, refresh resilience, storage, and chart data."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pandas as pd

from providers.repository_data import RepositoryScreenerProvider
from providers.screener import (
    HISTORY_COLUMNS,
    SUMMARY_COLUMNS,
    ScreenerCompanySnapshot,
    ScreenerDataError,
    ScreenerFundamentalsProvider,
    _cagr,
)
from scripts import refresh_screener_fundamentals
from ui.stock_detail import build_pe_eps_figure, filter_valuation_history


ANNUAL_HEADERS = "".join(
    f"<th>Mar {year}</th>" for year in range(2016, 2027)
)
ANNUAL_EPS = "".join(f"<td>{10 + year - 2016}</td>" for year in range(2016, 2027))

COMPANY_HTML = f"""
<html><body>
  <div id="company-info"
       data-company-id="2726"
       data-consolidated="true"></div>
  <ul id="top-ratios">
    <li><span class="name">Stock P/E</span><span class="number">20.0</span></li>
    <li><span class="name">ROE</span><span class="number">8.91%</span></li>
  </ul>
  <section id="profit-loss">
    <table>
      <thead><tr><th></th>{ANNUAL_HEADERS}<th>TTM</th></tr></thead>
      <tbody>
        <tr><td>EPS in Rs</td>{ANNUAL_EPS}<td>21</td></tr>
        <tr><td>OPM %</td>{ANNUAL_EPS}<td>16%</td></tr>
      </tbody>
    </table>
    <div>
      <div>Compounded Sales Growth</div>
      <span>10 Years:</span><span>15%</span>
      <span>5 Years:</span><span>18%</span>
      <span>3 Years:</span><span>6%</span>
      <span>TTM:</span><span>15%</span>
      <div>Compounded Profit Growth</div>
      <span>10 Years:</span><span>10%</span>
      <span>5 Years:</span><span>12%</span>
      <span>3 Years:</span><span>5%</span>
      <span>TTM:</span><span>0%</span>
    </div>
  </section>
  <section id="balance-sheet">
    <table>
      <thead><tr><th></th><th>Mar 2025</th><th>Mar 2026</th></tr></thead>
      <tbody>
        <tr><td>Equity Capital</td><td>10</td><td>10</td></tr>
        <tr><td>Reserves</td><td>800</td><td>890</td></tr>
        <tr><td>Borrowings</td><td>350</td><td>400</td></tr>
      </tbody>
    </table>
  </section>
</body></html>
"""


def chart_payload():
    dates = [f"{year}-07-01" for year in range(2016, 2027)]
    return {
        "datasets": [
            {
                "metric": "Price to Earning",
                "values": [
                    [date, 20 + index] for index, date in enumerate(dates)
                ],
            },
            {
                "metric": "EPS",
                "values": [
                    [date, 10 + index] for index, date in enumerate(dates)
                ],
            },
            {"metric": "Median PE", "values": [[dates[0], 25.0]]},
        ]
    }


class FakeResponse:
    def __init__(self, text="", payload=None, url="https://example.test"):
        self.text = text
        self._payload = payload
        self.url = url

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "/chart/" in url:
            return FakeResponse(payload=chart_payload(), url=url)
        return FakeResponse(text=COMPANY_HTML, url=url)


class ScreenerProviderTests(unittest.TestCase):
    def test_fetches_all_backend_metrics_and_chart_observations(self):
        provider = ScreenerFundamentalsProvider(
            session=FakeSession(), sleep=lambda _seconds: None
        )

        snapshot = provider.fetch(
            "RELIANCE.NS", refreshed_at="2026-07-24T00:00:00+00:00"
        )

        self.assertEqual(snapshot.summary["statement_type"], "consolidated")
        self.assertEqual(
            snapshot.summary["financial_reporting_date"], "2026-03-31"
        )
        self.assertEqual(snapshot.summary["sales_growth_3y"], 6.0)
        self.assertEqual(snapshot.summary["profit_growth_10y"], 10.0)
        self.assertAlmostEqual(snapshot.summary["debt_to_equity"], 400 / 900)
        self.assertEqual(snapshot.summary["roe"], 8.91)
        self.assertEqual(snapshot.summary["opm"], 16.0)
        self.assertNotIn("peg_ratio", snapshot.summary)
        self.assertAlmostEqual(
            snapshot.summary["eps_growth_10y"],
            ((20 / 10) ** (1 / 10) - 1) * 100,
        )
        self.assertIsNotNone(snapshot.summary["pe_average_3y"])
        self.assertIsNotNone(snapshot.summary["pe_median_10y"])
        self.assertEqual(tuple(snapshot.history.columns), HISTORY_COLUMNS)
        self.assertEqual(len(snapshot.history), 11)
        self.assertNotIn("pe_minimum_10y", snapshot.summary)
        self.assertNotIn("pe_maximum_10y", snapshot.summary)

    def test_invalid_eps_endpoints_do_not_create_misleading_cagr(self):
        self.assertIsNone(_cagr(-1, 10, 3))
        self.assertIsNone(_cagr(10, 0, 3))

    def test_retries_temporary_request_failures(self):
        session = Mock()
        session.get.side_effect = [
            __import__("requests").ConnectionError("temporary"),
            FakeResponse(text=COMPANY_HTML),
            FakeResponse(payload=chart_payload()),
        ]
        sleeps = []
        provider = ScreenerFundamentalsProvider(
            session=session, sleep=sleeps.append
        )

        provider.fetch("RELIANCE.NS", "2026-07-24T00:00:00+00:00")

        self.assertEqual(sleeps, [1])
        self.assertEqual(provider.metrics()["retries"], 1)


class FakeProvider:
    def __init__(self, failed=None):
        self.failed = set(failed or [])
        self.fetched = []

    def fetch(self, symbol, refreshed_at):
        self.fetched.append(symbol)
        if symbol in self.failed:
            raise ScreenerDataError(f"No Screener company for {symbol}")
        history = pd.DataFrame(
            {
                "symbol": [symbol, symbol],
                "date": pd.to_datetime(["2025-07-01", "2026-07-01"]),
                "pe": [20.0, 21.0],
                "ttm_eps": [10.0, 11.0],
            }
        )
        summary = {column: None for column in SUMMARY_COLUMNS}
        summary.update(
            {
                "symbol": symbol,
                "screener_company_id": symbol,
                "statement_type": "consolidated",
                "source_url": "https://www.screener.in/",
                "refreshed_at": refreshed_at,
            }
        )
        return ScreenerCompanySnapshot(summary=summary, history=history)

    def metrics(self):
        return {"requests": len(self.fetched), "retries": 0, "failures": 0}


class InterruptingProvider(FakeProvider):
    def __init__(self, interrupt_symbol):
        super().__init__()
        self.interrupt_symbol = interrupt_symbol

    def fetch(self, symbol, refreshed_at):
        if symbol == self.interrupt_symbol:
            self.fetched.append(symbol)
            raise KeyboardInterrupt()
        return super().fetch(symbol, refreshed_at)


class ScreenerRefreshTests(unittest.TestCase):
    def test_unified_refresh_throttles_batches_and_records_failures(self):
        symbols = ["A.NS", "B.NS", "C.NS", "D.NS", "E.NS"]
        provider = FakeProvider(failed={"D.NS"})
        sleeps = []
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = refresh_screener_fundamentals.refresh(
                symbols=symbols,
                root=root,
                provider=provider,
                batch_size=2,
                sleep_seconds=5,
                sleep=sleeps.append,
            )
            validated = refresh_screener_fundamentals.validate_snapshot(root)
            failure_file = root / manifest["coverage_file"]["path"]
            failures = pd.read_csv(failure_file)

        self.assertEqual(sleeps, [5, 5])
        self.assertEqual(manifest["successful_symbol_count"], 4)
        self.assertEqual(manifest["failed_symbol_count"], 1)
        self.assertEqual(manifest["batch_size"], 2)
        self.assertEqual(manifest["batch_sleep_seconds"], 5)
        self.assertEqual(failures["symbol"].tolist(), ["D.NS"])
        self.assertEqual(validated["historical_observation_count"], 8)

    def test_interrupted_refresh_resumes_after_completed_batch(self):
        symbols = ["A.NS", "B.NS", "C.NS", "D.NS"]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first_provider = InterruptingProvider("C.NS")
            with self.assertRaises(KeyboardInterrupt):
                refresh_screener_fundamentals.refresh(
                    symbols=symbols,
                    root=root,
                    provider=first_provider,
                    batch_size=2,
                    sleep_seconds=0,
                )
            checkpoint = json.loads(
                (root / ".staging" / "checkpoint.json").read_text()
            )
            second_provider = FakeProvider()
            manifest = refresh_screener_fundamentals.refresh(
                symbols=symbols,
                root=root,
                provider=second_provider,
                batch_size=2,
                sleep_seconds=0,
            )

        self.assertEqual(checkpoint["completed_symbols"], ["A.NS", "B.NS"])
        self.assertEqual(second_provider.fetched, ["C.NS", "D.NS"])
        self.assertEqual(manifest["successful_symbol_count"], 4)

    def test_repository_reads_one_symbol_from_committed_snapshot(self):
        symbols = ["A.NS", "B.NS"]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            refresh_screener_fundamentals.refresh(
                symbols=symbols,
                root=root,
                provider=FakeProvider(),
                batch_size=2,
                sleep_seconds=0,
            )
            repository = RepositoryScreenerProvider(root)

            history = repository.valuation_history("B.NS")
            summary = repository.fundamental_metrics("B.NS")

        self.assertEqual(history["symbol"].unique().tolist(), ["B.NS"])
        self.assertEqual(summary["statement_type"], "consolidated")


class HistoricalValuationChartTests(unittest.TestCase):
    def test_filters_period_and_builds_requested_chart_layers(self):
        history = pd.DataFrame(
            {
                "symbol": ["TEST.NS"] * 4,
                "date": pd.to_datetime(
                    ["2016-07-01", "2022-07-01", "2025-07-01", "2026-07-01"]
                ),
                "pe": [15.0, 20.0, 24.0, 22.0],
                "ttm_eps": [10.0, 12.0, 15.0, 17.0],
            }
        )

        selected = filter_valuation_history(history, "5Y")
        figure = build_pe_eps_figure(selected)

        self.assertEqual(selected["date"].min(), pd.Timestamp("2022-07-01"))
        self.assertEqual(
            {trace.name for trace in figure.data},
            {"P/E", "Median P/E = 22.0", "TTM EPS"},
        )
        self.assertEqual(figure.layout.yaxis.title.text, "TTM EPS")
        self.assertEqual(figure.layout.yaxis2.title.text, "P/E")


if __name__ == "__main__":
    unittest.main()
