"""Provider-independent historical replay engine."""

from __future__ import annotations

import pandas as pd

from stock_analyser.domain.backtesting.calculations import forward_returns, valuation_at, within_cross_age
from stock_analyser.domain.backtesting.models import BacktestRun, BacktestSignal
from stock_analyser.domain.backtesting.rules import qualifies_post_cross
from stock_analyser.domain.scanning.indicators import Indicators
from stock_analyser.domain.scanning.models import ScanConfig


class BacktestReplay:
    """Replay one symbol using only supplied historical observations."""

    def __init__(self, config: ScanConfig, *, qualifier=qualifies_post_cross) -> None:
        config.validate()
        self.config = config
        self._qualifier = qualifier

    def replay_symbol(
        self,
        symbol: str,
        prices: pd.DataFrame,
        valuation_history: pd.DataFrame | None = None,
    ) -> BacktestRun:
        run = BacktestRun()
        if prices.empty or not {"Open", "Close"}.issubset(prices.columns):
            run.failures[symbol] = "No complete Open/Close history is available"
            return run
        history = Indicators.add_moving_averages(
            prices.sort_index(), self.config.short_ma, self.config.long_ma
        )
        crosses = history["MA_SHORT"].shift(1).le(
            history["MA_LONG"].shift(1)
        ) & history["MA_SHORT"].gt(history["MA_LONG"])
        for cross_index in history.index[crosses]:
            cross_position = history.index.get_loc(cross_index)
            for position in range(cross_position, len(history) - 1):
                partial = history.iloc[: position + 1]
                if not within_cross_age(cross_index, partial.index[-1], self.config.max_cross_age):
                    break
                if not self._qualifier(partial, self.config):
                    continue
                entry_position = position + 1
                entry_price = history.iloc[entry_position]["Open"]
                if pd.isna(entry_price) or entry_price <= 0:
                    break
                pe, pe_date = valuation_at(valuation_history, partial.index[-1])
                run.signals.append(
                    BacktestSignal(
                        symbol,
                        cross_index.to_pydatetime(),
                        partial.index[-1].to_pydatetime(),
                        history.index[entry_position].to_pydatetime(),
                        float(entry_price),
                        forward_returns(history, entry_position, float(entry_price)),
                        pe,
                        pe_date,
                    )
                )
                break
        return run


__all__ = ["BacktestReplay"]
