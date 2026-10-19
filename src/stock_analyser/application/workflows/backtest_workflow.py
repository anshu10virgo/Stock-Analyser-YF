"""Coordinate one historical replay across injected providers."""

from __future__ import annotations

from stock_analyser.application.commands.run_backtest import (
    BacktestExecution,
    RunBacktest,
    RunBacktestCommand,
)


class BacktestWorkflow:
    def __init__(self, providers, *, runner_type=RunBacktest) -> None:
        self._providers = providers
        self._runner_type = runner_type

    def execute(self, command: RunBacktestCommand) -> BacktestExecution:
        return self._runner_type(
            self._providers.history,
            self._providers.screener,
        ).execute(command)
