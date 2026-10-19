"""Run historical Post-Cross replay without presentation concerns."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from services.backtest_service import BacktestService
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


class RunBacktest:
    def __init__(
        self,
        market_data,
        screener=None,
        *,
        service_type=BacktestService,
    ) -> None:
        self._market_data = market_data
        self._screener = screener
        self._service_type = service_type

    def execute(self, command: RunBacktestCommand) -> BacktestExecution:
        if command.years <= 0:
            raise ValueError("Backtest years must be positive")
        symbols = list(command.symbols)
        batch = self._market_data.download_batch(
            symbols,
            years=command.years + 2,
            adjusted_prices=False,
        )
        engine = self._service_type(command.config, self._screener)
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
            run = engine.replay_symbol(symbol, history)
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
        return BacktestExecution(pd.DataFrame(rows), charts, failures)
