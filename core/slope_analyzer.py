import numpy as np
from scipy.stats import linregress


class SlopeAnalyzer:

    @staticmethod
    def calculate_slope(
        series,
        lookback
    ):

        series = (
            series
            .dropna()
            .tail(lookback)
        )

        if len(series) < lookback:
            return 0

        x = np.arange(
            len(series)
        )

        slope = linregress(
            x,
            series.values
        ).slope

        return slope

    @staticmethod
    def classify_slope(
        slope
    ):

        if slope > 0.25:
            return "STRONG_POSITIVE"

        if slope > 0:
            return "POSITIVE"

        if slope > -0.25:
            return "FLAT"

        return "NEGATIVE"