"""Pure Long-MA decline and recovery rules."""

from __future__ import annotations

import pandas as pd

from stock_analyser.domain.scanning.indicators import SlopeAnalyzer
from stock_analyser.domain.scanning.models import LongMaReversal, RuleFailure


def evaluate_long_ma_reversal(
    history: pd.DataFrame,
    *,
    high_window_sessions: int = 252,
    recovery_slope_sessions: int = 5,
) -> LongMaReversal | None:
    """Measure the high-to-trough sequence and post-trough recovery."""
    long_ma = history["MA_LONG"].dropna()
    if len(long_ma) < high_window_sessions:
        return None
    window = long_ma.iloc[-high_window_sessions:]
    peak_value = float(window.max())
    peak_date = window[window == peak_value].index[-1]
    peak_age = len(window) - 1 - window.index.get_loc(peak_date)
    after_peak = window.loc[peak_date:]
    trough_value = float(after_peak.min())
    trough_date = after_peak[after_peak == trough_value].index[-1]
    decline_duration = window.index.get_loc(trough_date) - window.index.get_loc(
        peak_date
    )
    decline_percent = ((peak_value - trough_value) / peak_value) * 100
    post_trough = window.loc[window.index > trough_date]
    recovery_slope = None
    if len(post_trough) >= recovery_slope_sessions:
        recovery_slope = SlopeAnalyzer.calculate_slope(
            post_trough, recovery_slope_sessions
        )
    recovering = (
        float(window.iloc[-1]) > trough_value
        and recovery_slope is not None
        and recovery_slope > 0
    )
    return LongMaReversal(
        peak_value=peak_value,
        peak_date=peak_date,
        peak_age=peak_age,
        trough_value=trough_value,
        trough_date=trough_date,
        decline_duration=decline_duration,
        decline_percent=decline_percent,
        recovery_slope=recovery_slope,
        recovering=recovering,
    )


def validate_long_ma_reversal(
    reversal: LongMaReversal | None,
    *,
    is_post_cross: bool,
    current_long_ma: float,
    latest_long_ma_slope: float,
    minimum_decline_percent: float,
    minimum_decline_duration: int,
) -> RuleFailure | None:
    """Apply the shared reversal thresholds and setup-specific recovery rule."""
    if reversal is None:
        return RuleFailure(
            "Long MA Validation",
            "Insufficient Long MA history for 52-week high",
        )
    if reversal.decline_percent < minimum_decline_percent:
        return RuleFailure(
            "Long MA Validation",
            "Long MA decline from 52-week high to trough is below configured minimum",
        )
    if reversal.decline_duration < minimum_decline_duration:
        return RuleFailure(
            "Long MA Validation",
            "Long MA decline from 52-week high to trough is shorter than configured minimum duration",
        )
    if is_post_cross and not reversal.recovering:
        return RuleFailure(
            "Long MA Validation",
            "Post-trough 5-session Long MA slope is not positive",
        )
    if not is_post_cross and (
        current_long_ma < reversal.trough_value or latest_long_ma_slope < 0
    ):
        return RuleFailure(
            "Impending Golden Cross Validation",
            "Long MA is below its trough or its latest 5-session slope is negative",
        )
    return None
