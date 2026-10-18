"""Pure price indicators used by scanner and Backtester rules."""

from __future__ import annotations

from datetime import datetime

import numpy as np
from scipy.stats import linregress

from stock_analyser.domain.scanning.models import RuleFailure


class Indicators:
    @staticmethod
    def moving_average(series, period):
        return series.rolling(period).mean()

    @staticmethod
    def add_moving_averages(df, short_period, long_period):
        result = df.copy()
        result["MA_SHORT"] = Indicators.moving_average(
            result["Close"], short_period
        )
        result["MA_LONG"] = Indicators.moving_average(
            result["Close"], long_period
        )
        return result

    @staticmethod
    def distance_from_ma(price, ma):
        if ma == 0:
            return np.nan
        return ((price - ma) / ma) * 100

    @staticmethod
    def rolling_high(series, lookback=252):
        return series.rolling(lookback).max()

    @staticmethod
    def rolling_low(series, lookback=252):
        return series.rolling(lookback).min()


class SlopeAnalyzer:
    @staticmethod
    def calculate_slope(series, lookback):
        values = series.dropna().tail(lookback)
        if len(values) < lookback:
            return 0
        x_axis = np.arange(len(values))
        return linregress(x_axis, values.values).slope

    @staticmethod
    def classify_slope(slope):
        if slope > 0.25:
            return "STRONG_POSITIVE"
        if slope > 0:
            return "POSITIVE"
        if slope > -0.25:
            return "FLAT"
        return "NEGATIVE"


class GoldenCrossDetector:
    @staticmethod
    def find_cross(df, max_age_days, evaluation_date=None):
        result = {
            "valid": False,
            "cross_date": None,
            "days_since_cross": None,
        }
        if len(df) < 250:
            return result
        short_ma = df["MA_SHORT"]
        long_ma = df["MA_LONG"]
        cross_mask = short_ma.shift(1).le(long_ma.shift(1)) & short_ma.gt(long_ma)
        cross_dates = df.index[cross_mask]
        if len(cross_dates) == 0:
            return result
        cross_date = cross_dates[-1]
        as_of_date = evaluation_date or datetime.today().date()
        if hasattr(as_of_date, "date"):
            as_of_date = as_of_date.date()
        days_since = (as_of_date - cross_date.date()).days
        if days_since > max_age_days:
            return result
        result["valid"] = True
        result["cross_date"] = cross_date
        result["days_since_cross"] = days_since
        return result


def validate_short_ma_slope(short_ma_slope: float) -> RuleFailure | None:
    """Require the configured five-session Short-MA trajectory to be positive."""
    if short_ma_slope <= 0:
        return RuleFailure(
            "Short MA Validation",
            "Short MA 5-session slope is not positive",
        )
    return None


def validate_price(
    latest,
    maximum_premium_percent: float,
) -> tuple[float | None, RuleFailure | None]:
    """Require Close above the Long MA without exceeding the premium limit."""
    if latest["Close"] <= latest["MA_LONG"]:
        return None, RuleFailure(
            "Price Validation",
            "Close price is not above Long MA",
        )
    premium = Indicators.distance_from_ma(latest["Close"], latest["MA_LONG"])
    if premium > maximum_premium_percent:
        return None, RuleFailure(
            "Price Validation",
            "Close price is too far above Long MA",
        )
    return float(premium), None
