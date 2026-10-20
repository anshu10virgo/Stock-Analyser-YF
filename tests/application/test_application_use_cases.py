"""Characterization tests for the application command/query boundary."""

from __future__ import annotations

import unittest
from datetime import datetime
from email.message import EmailMessage
from types import SimpleNamespace

import pandas as pd

from stock_analyser.agents.action_models import AssistantAction
from stock_analyser.domain.backtesting import BacktestRun, BacktestSignal
from stock_analyser.domain.scanning.models import ScanConfig, ScanRun
from stock_analyser.application.commands.run_backtest import (
    RunBacktest,
    RunBacktestCommand,
)
from stock_analyser.application.commands.run_scan import RunScan, RunScanCommand
from stock_analyser.application.commands.send_report import (
    SendReport,
    SendReportCommand,
)
from stock_analyser.application.commands.update_strategy import apply_action
from stock_analyser.application.queries import (
    explain_failure_summary,
    get_data_health,
    get_scan_summary,
    get_stock_status,
)
from stock_analyser.application.workflows.refresh_workflow import (
    RefreshStep,
    RefreshWorkflow,
)
from stock_analyser.application.workflows.scan_workflow import ScanWorkflow


class ApplicationUseCaseTests(unittest.TestCase):
    def test_scan_command_passes_only_explicit_dependencies_and_inputs(self):
        captured = {}

        class Scanner:
            def __init__(self, config, **providers):
                captured["config"] = config
                captured["providers"] = providers

            def scan(self, symbols, **callbacks):
                captured["symbols"] = tuple(symbols)
                captured["callbacks"] = callbacks
                return "scan-run"

        config = ScanConfig(50, 200, 80, 60, 10, 10)
        dependencies = [object() for _ in range(4)]
        result = RunScan(*dependencies, service_type=Scanner).execute(
            RunScanCommand.create(["A.NS", "B.NS"], config)
        )

        self.assertEqual(result, "scan-run")
        self.assertIs(captured["config"], config)
        self.assertEqual(captured["symbols"], ("A.NS", "B.NS"))
        self.assertIs(captured["providers"]["data_provider"], dependencies[0])
        self.assertIs(
            captured["providers"]["fundamentals_provider"], dependencies[1]
        )

    def test_scan_workflow_returns_run_and_provider_metadata(self):
        providers = SimpleNamespace(
            history=object(),
            fundamentals=object(),
            industry_valuation=object(),
            screener=object(),
            metadata={"snapshot_id": "snapshot-1"},
        )

        class Runner:
            def __init__(self, *dependencies):
                self.dependencies = dependencies

            @staticmethod
            def execute(command, **callbacks):
                return ScanRun(metrics={"command_symbols": len(command.symbols)})

        config = ScanConfig(50, 200, 80, 60, 10, 10)
        result = ScanWorkflow(providers, runner_type=Runner).execute(
            RunScanCommand.create(["A.NS"], config)
        )
        self.assertEqual(result.run.metrics["command_symbols"], 1)
        self.assertEqual(result.provider_metadata["snapshot_id"], "snapshot-1")

    def test_backtest_command_returns_rows_charts_and_failures(self):
        dates = pd.date_range("2025-01-01", periods=5, freq="B")
        history = pd.DataFrame(
            {"Open": [100, 101, 102, 103, 104], "Close": [100, 102, 103, 104, 105]},
            index=dates,
        )

        class MarketData:
            def download_batch(self, symbols, **options):
                self.options = options
                return {symbols[0]: history}

            @staticmethod
            def get_symbol_history(batch, symbol):
                return batch[symbol]

        class Backtester:
            def __init__(self, config, screener):
                pass

            @staticmethod
            def replay_symbol(symbol, prices):
                signal = BacktestSignal(
                    symbol,
                    dates[0].to_pydatetime(),
                    dates[1].to_pydatetime(),
                    dates[2].to_pydatetime(),
                    102.0,
                    {"1Y": 5.0},
                )
                return BacktestRun([signal], {})

        config = ScanConfig(50, 200, 80, 60, 10, 10)
        market_data = MarketData()
        execution = RunBacktest(
            market_data, service_type=Backtester
        ).execute(
            RunBacktestCommand(("A.NS",), 3, config, {"A.NS": "Alpha"})
        )

        self.assertEqual(execution.results.iloc[0]["Company"], "Alpha")
        self.assertIn("A.NS", execution.charts)
        self.assertEqual(execution.failures, {})
        self.assertEqual(market_data.options["years"], 5)
        self.assertFalse(market_data.options["adjusted_prices"])

    def test_queries_preserve_current_scan_outputs(self):
        state = {
            "scan_time": datetime(2026, 10, 19, 8, 0),
            "scan_results": pd.DataFrame(
                [{"symbol": "A.NS", "company_name": "Alpha", "close": 100}]
            ),
            "scan_impending_results": pd.DataFrame(),
            "scan_failed_results": pd.DataFrame(
                [
                    {
                        "symbol": "B.NS",
                        "stage": "Short MA Validation",
                        "reason": "Short MA 5-session slope is not positive",
                    }
                ]
            ),
            "scan_metrics": {"timing": {"total_seconds": 1.5}},
        }

        self.assertEqual(get_scan_summary(state)["post_golden_cross_count"], 1)
        self.assertEqual(get_stock_status(state, "Alpha")["status"], "Post Golden Cross")
        self.assertEqual(
            explain_failure_summary(state)["reasons"][0]["reason"],
            "Short MA is not rising",
        )
        self.assertEqual(
            get_data_health(state, snapshot_identity="snapshot-1")[
                "snapshot_identity"
            ],
            "snapshot-1",
        )

    def test_strategy_command_requires_a_valid_config_before_mutation(self):
        state = {"selected_symbols": ["A.NS"], "stock_count": 1}
        settings = {
            "short_ma": 200,
            "long_ma": 50,
            "cross_age": 80,
            "min_long_ma_decline_duration": 60,
            "min_long_ma_decline": 10,
            "max_price_premium": 10,
            "include_impending_crosses": False,
            "impending_max_gap_pct": 10,
            "pre_cross_validation_sessions": 20,
            "optional_filters": [],
            "adjusted_prices": False,
        }
        with self.assertRaises(ValueError):
            apply_action(AssistantAction("strategy", "invalid", settings=settings), state)
        self.assertNotIn("_next_app_section", state)

    def test_send_report_uses_the_mailer_port(self):
        sent = []

        class Mailer:
            @staticmethod
            def send(messages):
                sent.extend(messages)

        message = EmailMessage()
        count = SendReport(Mailer()).execute(SendReportCommand((message,)))
        self.assertEqual(count, 1)
        self.assertEqual(sent, [message])

    def test_refresh_workflow_runs_explicit_steps_in_order(self):
        called = []
        result = RefreshWorkflow(
            (
                RefreshStep("prices", lambda: called.append("prices") or 1),
                RefreshStep("fundamentals", lambda: called.append("fundamentals") or 2),
            )
        ).execute()
        self.assertEqual(called, ["prices", "fundamentals"])
        self.assertEqual(result, {"prices": 1, "fundamentals": 2})


if __name__ == "__main__":
    unittest.main()
