import pandas as pd

from core.data_loader import DataLoader
from core.indicators import Indicators
from core.golden_cross import GoldenCrossDetector
from core.slope_analyzer import SlopeAnalyzer
from core.trough_detector import TroughDetector
from core.fundamentals import Fundamentals
from core.scoring import ScoringEngine


class StockScanner:

    def __init__(
        self,
        short_ma,
        long_ma,
        max_cross_age,
        pre_cross_days,
        trough_lookback,
        min_troughs,
        slope_lookback,
        max_distance,
        adjusted_prices=False,
    ):

        self.short_ma = short_ma
        self.long_ma = long_ma

        self.max_cross_age = max_cross_age

        self.pre_cross_days = pre_cross_days

        self.trough_lookback = trough_lookback

        self.min_troughs = min_troughs

        self.slope_lookback = slope_lookback

        self.max_distance = max_distance

        self.adjusted_prices = adjusted_prices

    def scan(
        self,
        symbols,
        progress_callback=None
    ):

        results = []
        failed_results = []

        batch_data = (
            DataLoader.download_batch(
                symbols,
                adjusted_prices=self.adjusted_prices,
            )
        )

        for index, symbol in enumerate(symbols):

            if progress_callback:
                progress_callback(
                    index + 1,
                    len(symbols)
                )
            try:

                df = (
                    DataLoader
                    .get_symbol_history(
                        batch_data,
                        symbol
                    )
                )

                if df.empty:
                    continue

                df = (
                    Indicators
                    .add_moving_averages(
                        df,
                        self.short_ma,
                        self.long_ma
                    )
                )

                cross = (
                    GoldenCrossDetector
                    .find_cross(
                        df,
                        self.max_cross_age,
                        self.pre_cross_days
                    )
                )

                if not cross["valid"]:
                    failed_results.append({
                        "symbol": symbol,
                        "reason": "Golden Cross validation failed"
                    })

                latest = df.iloc[-1]

                distance = (
                    Indicators
                    .distance_from_ma(
                        latest["Close"],
                        latest["MA_LONG"]
                    )
                )

                if abs(distance) > self.max_distance:
                    continue

                troughs = (
                    TroughDetector
                    .detect_troughs(
                        df,
                        self.trough_lookback
                    )
                )

                if (
                    troughs["count"]
                    <
                    self.min_troughs
                ):
                    continue

                slope = (
                    SlopeAnalyzer
                    .calculate_slope(
                        df["MA_LONG"],
                        self.slope_lookback
                    )
                )

                slope_label = (
                    SlopeAnalyzer
                    .classify_slope(
                        slope
                    )
                )

                fundamentals = (
                    Fundamentals
                    .get_fundamentals(
                        symbol
                    )
                )

                score = 0

                score += (
                    ScoringEngine
                    .score_cross(
                        cross["days_since_cross"]
                    )
                )

                score += (
                    ScoringEngine
                    .score_slope(
                        slope_label
                    )
                )

                score += (
                    ScoringEngine
                    .score_troughs(
                        troughs["count"]
                    )
                )

                score += (
                    ScoringEngine
                    .score_distance(
                        distance
                    )
                )

                score += (
                    ScoringEngine
                    .score_pe(
                        fundamentals["pe"]
                    )
                )

                score += (
                    ScoringEngine
                    .score_eps(
                        fundamentals["eps"]
                    )
                )

                score += (
                    ScoringEngine
                    .score_market_cap(
                        fundamentals["market_cap"]
                    )
                )

                results.append({

                    "symbol": symbol,

                    "close":
                        round(
                            latest["Close"],
                            2
                        ),

                    "ma_short":
                        round(
                            latest["MA_SHORT"],
                            2
                        ),

                    "ma_long":
                        round(
                            latest["MA_LONG"],
                            2
                        ),

                    "cross_date":
                        cross["cross_date"],

                    "days_since_cross":
                        cross["days_since_cross"],

                    "distance_from_ma":
                        round(
                            distance,
                            2
                        ),

                    "trough_count":
                        troughs["count"],

                    "slope":
                        round(
                            slope,
                            4
                        ),

                    "slope_label":
                        slope_label,

                    "market_cap":
                        fundamentals["market_cap"],

                    "pe":
                        fundamentals["pe"],

                    "eps":
                        fundamentals["eps"],

                    "sector":
                        fundamentals["sector"],

                    "industry":
                        fundamentals["industry"],

                    "score":
                        score

                })

            except Exception as ex:

                print(
                    symbol,
                    ex
                )

        passed_df = pd.DataFrame(results)
        failed_df = pd.DataFrame(failed_results)


        if not passed_df.empty:

            passed_df.sort_values(
                by="score",
                ascending=False,
                inplace=True
            )

            passed_df.reset_index(
                drop=True,
                inplace=True
            )

        return {
            "passed": passed_df,
            "failed": failed_df
        }
