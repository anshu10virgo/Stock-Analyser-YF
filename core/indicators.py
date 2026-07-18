import pandas as pd
import numpy as np


class Indicators:

    @staticmethod
    def moving_average(
        series,
        period
    ):
        return (
            series
            .rolling(period)
            .mean()
        )

    @staticmethod
    def add_moving_averages(
        df,
        short_period,
        long_period
    ):

        df = df.copy()

        df["MA_SHORT"] = (
            Indicators.moving_average(
                df["Close"],
                short_period
            )
        )

        df["MA_LONG"] = (
            Indicators.moving_average(
                df["Close"],
                long_period
            )
        )

        return df

    @staticmethod
    def distance_from_ma(
        price,
        ma
    ):

        if ma == 0:
            return np.nan

        return (
            (price - ma)
            / ma
        ) * 100

    @staticmethod
    def rolling_high(
        series,
        lookback=252
    ):

        return (
            series
            .rolling(lookback)
            .max()
        )

    @staticmethod
    def rolling_low(
        series,
        lookback=252
    ):

        return (
            series
            .rolling(lookback)
            .min()
        )