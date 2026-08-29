"""Historical replay for the complete Post Golden Cross strategy."""

from __future__ import annotations

import pandas as pd

from core.indicators import Indicators
from core.slope_analyzer import SlopeAnalyzer
from models.backtest import BacktestRun, BacktestSignal, HORIZON_SESSIONS
from models.scan_config import ScanConfig
from services.scan_service import ScanService


class BacktestService:
    """Evaluate each close using only information available at that close."""

    def __init__(self, config: ScanConfig, screener_provider=None) -> None:
        config.validate()
        self.config = config
        self.screener_provider = screener_provider
        self._scanner = ScanService(config)

    def _qualifies(self, history: pd.DataFrame) -> bool:
        latest = history.iloc[-1]
        if len(history) < self.config.long_ma or latest["MA_SHORT"] <= latest["MA_LONG"]:
            return False
        if SlopeAnalyzer.calculate_slope(history["MA_SHORT"], 5) <= 0:
            return False
        reversal = self._scanner._long_ma_reversal(history)
        if reversal is None:
            return False
        _, _, _, trough, _, duration, decline, _, recovering = reversal
        if duration < self.config.min_long_ma_decline_duration or decline < self.config.min_long_ma_decline:
            return False
        if not recovering or latest["Close"] <= latest["MA_LONG"]:
            return False
        premium = Indicators.distance_from_ma(latest["Close"], latest["MA_LONG"])
        return premium <= self.config.max_price_premium

    def _within_cross_age(self, cross_date: pd.Timestamp, evaluation_date: pd.Timestamp) -> bool:
        return (evaluation_date - cross_date).days <= self.config.max_cross_age

    def _pe_at(self, symbol: str, signal_date: pd.Timestamp):
        if self.screener_provider is None:
            return None, None
        history = self.screener_provider.valuation_history(symbol)
        history = history.loc[history["date"].le(signal_date) & history["pe"].gt(0)]
        if history.empty:
            return None, None
        latest = history.iloc[-1]
        return float(latest["pe"]), latest["date"].to_pydatetime()

    @staticmethod
    def _forward_returns(history: pd.DataFrame, entry_position: int, entry_price: float) -> dict[str, float | None]:
        returns = {}
        for label, sessions in HORIZON_SESSIONS.items():
            exit_position = entry_position + sessions
            returns[label] = None if exit_position >= len(history) else round(((history.iloc[exit_position]["Close"] / entry_price) - 1) * 100, 2)
        return returns

    def replay_symbol(self, symbol: str, prices: pd.DataFrame) -> BacktestRun:
        run = BacktestRun()
        if prices.empty or not {"Open", "Close"}.issubset(prices.columns):
            run.failures[symbol] = "No complete Open/Close history is available"
            return run
        history = Indicators.add_moving_averages(prices.sort_index(), self.config.short_ma, self.config.long_ma)
        crosses = (history["MA_SHORT"].shift(1).le(history["MA_LONG"].shift(1)) & history["MA_SHORT"].gt(history["MA_LONG"]))
        for cross_index in history.index[crosses]:
            cross_position = history.index.get_loc(cross_index)
            for position in range(cross_position, len(history) - 1):
                partial = history.iloc[: position + 1]
                if not self._within_cross_age(cross_index, partial.index[-1]):
                    break
                if not self._qualifies(partial):
                    continue
                entry_position = position + 1
                entry_price = history.iloc[entry_position]["Open"]
                if pd.isna(entry_price) or entry_price <= 0:
                    break
                returns = self._forward_returns(history, entry_position, float(entry_price))
                pe, pe_date = self._pe_at(symbol, partial.index[-1])
                run.signals.append(BacktestSignal(symbol, cross_index.to_pydatetime(), partial.index[-1].to_pydatetime(), history.index[entry_position].to_pydatetime(), float(entry_price), returns, pe, pe_date))
                break
        return run
