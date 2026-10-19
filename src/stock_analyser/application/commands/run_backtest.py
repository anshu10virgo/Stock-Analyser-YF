"""Run historical Post-Cross replay without presentation concerns."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from stock_analyser.domain.backtesting import BacktestReplay, ReturnSummary, summarize_returns
from stock_analyser.domain.scanning.indicators import Indicators
from stock_analyser.domain.scanning.models import ScanConfig


@dataclass(frozen=True)
class RunBacktestCommand:
    symbols: tuple[str, ...]
    years: int
    config: ScanConfig
    company_names: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BacktestExecution:
    results: pd.DataFrame
    charts: dict[str, pd.DataFrame]
    failures: dict[str, str]
    one_year_summary: ReturnSummary | None = None


class RunBacktest:
    def __init__(
        self,
        market_data,
        screener=None,
        *,
        service_type=None,
        replay_type=BacktestReplay,
    ) -> None:
        self._market_data = market_data
        self._screener = screener
        self._service_type = service_type
        self._replay_type = replay_type

    def execute(self, command: RunBacktestCommand) -> BacktestExecution:
        if command.years <= 0:
            raise ValueError("Backtest years must be positive")
        symbols = list(command.symbols)
        batch = self._market_data.download_batch(
            symbols,
            years=command.years + 2,
            adjusted_prices=False,
        )
        engine = (
            self._service_type(command.config, self._screener)
            if self._service_type is not None
            else self._replay_type(command.config)
        )
        rows: list[dict] = []
        charts: dict[str, pd.DataFrame] = {}
        failures: dict[str, str] = {}
        for symbol in symbols:
            history = self._market_data.get_symbol_history(batch, symbol)
            charts[symbol] = Indicators.add_moving_averages(
                history,
                command.config.short_ma,
                command.config.long_ma,
            )
            if self._service_type is not None:
                run = engine.replay_symbol(symbol, history)
            else:
                valuations = (
                    self._screener.valuation_history(symbol)
                    if self._screener is not None
                    else None
                )
                run = engine.replay_symbol(symbol, history, valuations)
            failures.update(run.failures)
            for signal in run.signals:
                rows.append(
                    {
                        "Stock": symbol,
                        "Company": command.company_names.get(symbol),
                        "Cross date": signal.cross_date.date(),
                        "Signal date": signal.signal_date.date(),
                        "Entry": signal.entry_price,
                        "P/E": signal.pe,
                        **signal.returns,
                    }
                )
        results = pd.DataFrame(rows)
        one_year_values = (
            results["1Y"] if "1Y" in results else pd.Series(dtype=float)
        )
        summary = summarize_returns(one_year_values, signal_count=len(results))
        return BacktestExecution(results, charts, failures, summary)
