"""Pure historical Post-Cross qualification rules."""

import pandas as pd

from stock_analyser.domain.scanning.indicators import Indicators, SlopeAnalyzer
from stock_analyser.domain.scanning.models import ScanConfig
from stock_analyser.domain.scanning.reversal_rules import evaluate_long_ma_reversal


def qualifies_post_cross(history: pd.DataFrame, config: ScanConfig) -> bool:
    latest = history.iloc[-1]
    if len(history) < config.long_ma or latest["MA_SHORT"] <= latest["MA_LONG"]:
        return False
    if SlopeAnalyzer.calculate_slope(history["MA_SHORT"], 5) <= 0:
        return False
    reversal = evaluate_long_ma_reversal(history)
    if reversal is None:
        return False
    if (
        reversal.decline_duration < config.min_long_ma_decline_duration
        or reversal.decline_percent < config.min_long_ma_decline
    ):
        return False
    if not reversal.recovering or latest["Close"] <= latest["MA_LONG"]:
        return False
    premium = Indicators.distance_from_ma(latest["Close"], latest["MA_LONG"])
    return premium <= config.max_price_premium


__all__ = ["qualifies_post_cross"]
