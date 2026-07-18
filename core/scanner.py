import pandas as pd

from core.data_loader import DataLoader
from core.indicators import Indicators
from core.golden_cross import GoldenCrossDetector
from core.slope_analyzer import SlopeAnalyzer
from core.trough_detector import TroughDetector
from core.fundamentals import Fundamentals
from core.scoring import ScoringEngine


class StockScanner:

    MIN_POST_CROSS_DAYS = 10

    def __init__(
        self,
        short_ma,
        long_ma,
        max_cross_age,
        pre_cross_days,
        slope_lookback,
        max_distance,
        require_pre_cross_trough=False,
        require_pre_cross_decline=False,
        require_post_cross_sessions=False,
        require_post_cross_increase=False,
        adjusted_prices=False,
    ):

        self.short_ma = short_ma
        self.long_ma = long_ma

        self.max_cross_age = max_cross_age

        self.pre_cross_days = pre_cross_days

        self.slope_lookback = slope_lookback

        self.max_distance = max_distance

        self.require_pre_cross_trough = require_pre_cross_trough
        self.require_pre_cross_decline = require_pre_cross_decline
        self.require_post_cross_sessions = require_post_cross_sessions
        self.require_post_cross_increase = require_post_cross_increase

        self.adjusted_prices = adjusted_prices

    def _find_pre_cross_trough(self, df, cross_date):
        """Return a validated trough from the configured pre-cross window."""
        cross_position = df.index.get_loc(cross_date)
        start_position = max(0, cross_position - self.pre_cross_days)
        pre_cross_df = df.iloc[start_position:cross_position + 1]
        troughs = TroughDetector.detect_troughs(pre_cross_df)

        dates = [date for date in troughs["dates"] if date < cross_date]
        return dates[-1] if dates else None

    def _long_ma_slopes(self, df, cross_date):
        """Return long-MA slopes and available post-cross trading sessions."""
        cross_position = df.index.get_loc(cross_date)
        pre_cross_ma = df.iloc[
            max(0, cross_position - self.slope_lookback):cross_position
        ]["MA_LONG"]
        post_cross_ma = df.iloc[cross_position + 1:]["MA_LONG"]

        pre_cross_slope = None
        if len(pre_cross_ma) >= self.slope_lookback:
            pre_cross_slope = SlopeAnalyzer.calculate_slope(
                pre_cross_ma,
                self.slope_lookback,
            )

        post_cross_slope = None
        if len(post_cross_ma) >= 2:
            post_cross_slope = SlopeAnalyzer.calculate_slope(
                post_cross_ma,
                len(post_cross_ma),
            )

        return pre_cross_slope, post_cross_slope, len(post_cross_ma)

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
                        "stage": "Golden Cross Validation",
                        "reason": "Golden Cross validation failed",
                        "check_type": "mandatory",
                    })
                    continue

                latest = df.iloc[-1]

                cross_close = df.loc[cross["cross_date"], "Close"]
                if latest["Close"] < cross_close:
                    failed_results.append({
                        "symbol": symbol,
                        "stage": "Price Validation",
                        "reason": "Close price is below Golden Cross close",
                        "check_type": "mandatory",
                    })
                    continue

                if latest["Close"] < latest["MA_SHORT"]:
                    failed_results.append({
                        "symbol": symbol,
                        "stage": "Price Validation",
                        "reason": "Close price is below Short MA",
                        "check_type": "mandatory",
                    })
                    continue

                if latest["MA_SHORT"] < latest["MA_LONG"]:
                    failed_results.append({
                        "symbol": symbol,
                        "stage": "Golden Cross Validation",
                        "reason": "Golden Cross has been invalidated by a Death Cross",
                        "check_type": "mandatory",
                    })
                    continue

                pre_cross_trough_date = None
                if self.require_pre_cross_trough:
                    pre_cross_trough_date = self._find_pre_cross_trough(
                        df,
                        cross["cross_date"],
                    )
                if self.require_pre_cross_trough and pre_cross_trough_date is None:
                    failed_results.append({
                        "symbol": symbol,
                        "stage": "Trough Validation",
                        "reason": "No trough found before Golden Cross",
                        "check_type": "optional",
                    })
                    continue

                pre_cross_slope, post_cross_slope, post_cross_days = (
                    self._long_ma_slopes(
                        df,
                        cross["cross_date"],
                    )
                )
                if self.require_pre_cross_decline and pre_cross_slope is None:
                    failed_results.append({
                        "symbol": symbol,
                        "stage": "Slope Validation",
                        "reason": "Insufficient history for pre-cross MA slope",
                        "check_type": "optional",
                    })
                    continue

                if self.require_pre_cross_decline and pre_cross_slope >= 0:
                    failed_results.append({
                        "symbol": symbol,
                        "stage": "Slope Validation",
                        "reason": "Long MA was not declining before Golden Cross",
                        "check_type": "optional",
                    })
                    continue

                if (
                    self.require_post_cross_sessions
                    and post_cross_days < self.MIN_POST_CROSS_DAYS
                ):
                    failed_results.append({
                        "symbol": symbol,
                        "stage": "Slope Validation",
                        "reason": "Golden Cross needs 10 post-cross sessions",
                        "check_type": "optional",
                    })
                    continue

                if self.require_post_cross_increase and post_cross_slope is None:
                    failed_results.append({
                        "symbol": symbol,
                        "stage": "Slope Validation",
                        "reason": "Insufficient post-cross history for MA slope",
                        "check_type": "optional",
                    })
                    continue

                if self.require_post_cross_increase and post_cross_slope <= 0:
                    failed_results.append({
                        "symbol": symbol,
                        "stage": "Slope Validation",
                        "reason": "Long MA is not increasing after Golden Cross",
                        "check_type": "optional",
                    })
                    continue

                distance = (
                    Indicators
                    .distance_from_ma(
                        latest["Close"],
                        latest["MA_LONG"]
                    )
                )

                if abs(distance) > self.max_distance:
                    failed_results.append({
                        "symbol": symbol,
                        "stage": "Price Validation",
                        "reason": "Close price is too far from Long MA",
                        "check_type": "mandatory",
                    })
                    continue

                score_slope = post_cross_slope
                if score_slope is None:
                    score_slope = SlopeAnalyzer.calculate_slope(
                        df["MA_LONG"],
                        self.slope_lookback,
                    )

                slope_label = (
                    SlopeAnalyzer
                    .classify_slope(
                        score_slope
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

                    "company_name": fundamentals["company_name"],

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

                    "slope":
                        round(
                            score_slope,
                            4
                        ),

                    "pre_cross_slope":
                        round(
                            pre_cross_slope,
                            4
                        ) if pre_cross_slope is not None else None,

                    "pre_cross_trough_date": pre_cross_trough_date,

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
