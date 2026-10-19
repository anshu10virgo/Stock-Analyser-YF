"""Compatibility facade for the canonical Backtesting domain replay engine."""

from __future__ import annotations

import pandas as pd

from stock_analyser.domain.backtesting import (
    BacktestReplay,
    forward_returns,
    qualifies_post_cross,
    valuation_at,
    within_cross_age,
)
from stock_analyser.domain.scanning.models import ScanConfig


class BacktestService:
    """Retain the established API while delegating calculations to the domain."""

    def __init__(self, config: ScanConfig, screener_provider=None) -> None:
        self.config = config
        self.screener_provider = screener_provider

    def _qualifies(self, history: pd.DataFrame) -> bool:
        return qualifies_post_cross(history, self.config)

    def _within_cross_age(self, cross_date, evaluation_date) -> bool:
        return within_cross_age(cross_date, evaluation_date, self.config.max_cross_age)

    def _pe_at(self, symbol: str, signal_date):
        history = None
        if self.screener_provider is not None:
            history = self.screener_provider.valuation_history(symbol)
        return valuation_at(history, signal_date)

    @staticmethod
    def _forward_returns(
        history: pd.DataFrame,
        entry_position: int,
        entry_price: float,
    ) -> dict[str, float | None]:
        return forward_returns(history, entry_position, entry_price)

    def replay_symbol(self, symbol: str, prices: pd.DataFrame):
        valuation_history = None
        if self.screener_provider is not None:
            valuation_history = self.screener_provider.valuation_history(symbol)
        replay = BacktestReplay(
            self.config,
            qualifier=lambda history, _config: self._qualifies(history),
        )
        return replay.replay_symbol(symbol, prices, valuation_history)


__all__ = ["BacktestService"]
