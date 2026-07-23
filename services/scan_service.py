"""Application service for configured stock scans."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Iterable

from core.data_loader import DataLoader
from core.fundamentals import Fundamentals
from core.golden_cross import GoldenCrossDetector
from core.indicators import Indicators
from core.scoring import ScoringEngine
from core.slope_analyzer import SlopeAnalyzer
from models.failure_result import FailureResult
from models.scan_config import ScanConfig
from models.scan_results import ScanResult
from models.scan_run import ScanRun
from services.industry_valuation import IndustryValuationService


logger = logging.getLogger(__name__)


class ScanService:
    """Coordinates market data, technical rules, fundamentals, and ranking."""

    MIN_POST_CROSS_DAYS = 10
    SHORT_MA_SLOPE_SESSIONS = 5
    LONG_MA_52_WEEK_SESSIONS = 252
    LONG_MA_RECOVERY_SLOPE_SESSIONS = 5
    SCORE_SLOPE_LOOKBACK = 20
    HISTORY_SAFETY_SESSIONS = 50
    CONSERVATIVE_TRADING_SESSIONS_PER_YEAR = 230

    def __init__(
        self,
        config: ScanConfig,
        data_provider=DataLoader,
        fundamentals_provider=Fundamentals,
        industry_valuation_service=None,
    ):
        config.validate()
        self.config = config
        self.data_provider = data_provider
        self.fundamentals_provider = fundamentals_provider
        self.industry_valuation_service = industry_valuation_service or IndustryValuationService()

    @staticmethod
    def _failure(symbol, stage, reason, check_type="mandatory"):
        return FailureResult(symbol, stage, reason, check_type)

    def _long_ma_reversal(self, history):
        """Return the 52-week Long-MA high, its trough, and current recovery."""
        long_ma = history["MA_LONG"].dropna()
        if len(long_ma) < self.LONG_MA_52_WEEK_SESSIONS:
            return None

        window = long_ma.iloc[-self.LONG_MA_52_WEEK_SESSIONS:]
        peak_value = window.max()
        peak_date = window[window == peak_value].index[-1]
        peak_age = len(window) - 1 - window.index.get_loc(peak_date)
        after_peak = window.loc[peak_date:]
        trough_value = after_peak.min()
        trough_date = after_peak[after_peak == trough_value].index[-1]
        decline_duration = window.index.get_loc(trough_date) - window.index.get_loc(peak_date)
        decline_percent = ((peak_value - trough_value) / peak_value) * 100
        post_trough = window.loc[window.index > trough_date]
        recovery_slope = None
        if len(post_trough) >= self.LONG_MA_RECOVERY_SLOPE_SESSIONS:
            recovery_slope = SlopeAnalyzer.calculate_slope(
                post_trough,
                self.LONG_MA_RECOVERY_SLOPE_SESSIONS,
            )
        long_ma_recovering = (
            window.iloc[-1] > trough_value
            and recovery_slope is not None
            and recovery_slope > 0
        )
        return (
            peak_value,
            peak_date,
            peak_age,
            trough_value,
            trough_date,
            decline_duration,
            decline_percent,
            recovery_slope,
            long_ma_recovering,
        )

    def _score(self, cross, slope_label, distance, fundamentals):
        return ScoringEngine.score_breakdown(
            cross["days_since_cross"],
            slope_label,
            distance,
            fundamentals,
        )

    def scan(
        self,
        symbols: Iterable[str],
        progress_callback: Callable[[int, int], None] | None = None,
        result_callback: Callable[[int, int, ScanRun], None] | None = None,
    ) -> ScanRun:
        """Scan symbols and optionally publish progress and accumulated results."""
        symbols = list(symbols)
        run = ScanRun()
        scan_started = time.perf_counter()
        if hasattr(self.industry_valuation_service, "begin_scan"):
            self.industry_valuation_service.begin_scan()
        if not symbols:
            run.metrics["timing"] = {
                "data_load_seconds": 0.0,
                "rule_evaluation_seconds": 0.0,
                "total_seconds": 0.0,
            }
            return run
        data_load_started = time.perf_counter()
        try:
            required_sessions = (
                self.config.long_ma
                + self.LONG_MA_52_WEEK_SESSIONS
                + self.HISTORY_SAFETY_SESSIONS
            )
            history_years = max(
                3,
                math.ceil(
                    required_sessions / self.CONSERVATIVE_TRADING_SESSIONS_PER_YEAR
                ),
            )
            batch_data = self.data_provider.download_batch(
                symbols,
                years=history_years,
                adjusted_prices=self.config.adjusted_prices,
            )
            if hasattr(self.data_provider, "market_data_metrics"):
                run.metrics["market_data"] = self.data_provider.market_data_metrics()
        except Exception:
            data_load_finished = time.perf_counter()
            logger.exception("Batch market-data download failed")
            run.failed.extend(self._failure(symbol, "Market Data", "Unable to download market data for this scan") for symbol in symbols)
            if hasattr(self.data_provider, "market_data_metrics"):
                run.metrics["market_data"] = self.data_provider.market_data_metrics()
            if hasattr(self.industry_valuation_service, "metrics"):
                run.metrics["industry_valuations"] = self.industry_valuation_service.metrics()
            run.metrics["timing"] = {
                "data_load_seconds": data_load_finished - data_load_started,
                "rule_evaluation_seconds": 0.0,
                "total_seconds": time.perf_counter() - scan_started,
            }
            return run
        data_load_finished = time.perf_counter()
        for index, symbol in enumerate(symbols, start=1):
            if progress_callback:
                progress_callback(index, len(symbols))
            self._scan_symbol(batch_data, symbol, run)
            if result_callback:
                result_callback(index, len(symbols), run)
        if hasattr(self.industry_valuation_service, "metrics"):
            run.metrics["industry_valuations"] = self.industry_valuation_service.metrics()
        run.metrics["timing"] = {
            "data_load_seconds": data_load_finished - data_load_started,
            "rule_evaluation_seconds": time.perf_counter() - data_load_finished,
            "total_seconds": time.perf_counter() - scan_started,
        }
        return run

    def _scan_symbol(self, batch_data, symbol, run):
        try:
            history = self.data_provider.get_symbol_history(batch_data, symbol)
            if history.empty:
                run.failed.append(self._failure(symbol, "Market Data", "No complete market data was returned for the symbol"))
                return
            history = Indicators.add_moving_averages(history, self.config.short_ma, self.config.long_ma)
            latest = history.iloc[-1]
            short_ma_slope = SlopeAnalyzer.calculate_slope(
                history["MA_SHORT"], self.SHORT_MA_SLOPE_SESSIONS
            )
            long_ma_slope = SlopeAnalyzer.calculate_slope(
                history["MA_LONG"], self.LONG_MA_RECOVERY_SLOPE_SESSIONS
            )
            if short_ma_slope <= 0:
                run.failed.append(self._failure(symbol, "Short MA Validation", "Short MA 5-session slope is not positive"))
                return
            is_post_cross = latest["MA_SHORT"] > latest["MA_LONG"]
            if is_post_cross:
                cross = GoldenCrossDetector.find_cross(history, self.config.max_cross_age)
                if not cross["valid"]:
                    run.failed.append(self._failure(symbol, "Post Golden Cross Validation", "No Golden Cross within the configured age"))
                    return
                cross_date = cross["cross_date"]
                strategy = "Post Golden Cross"
            else:
                if not self.config.include_impending_crosses:
                    run.failed.append(self._failure(symbol, "Post Golden Cross Validation", "Short MA is not above Long MA"))
                    return
                gap_percent = (
                    (latest["MA_LONG"] - latest["MA_SHORT"])
                    / latest["MA_LONG"]
                ) * 100
                if gap_percent > self.config.impending_max_gap_pct:
                    run.failed.append(self._failure(symbol, "Impending Golden Cross Validation", "Short MA is farther below Long MA than the configured maximum gap"))
                    return
                if short_ma_slope <= long_ma_slope:
                    run.failed.append(self._failure(symbol, "Impending Golden Cross Validation", "Short MA 5-session slope is not greater than Long MA 5-session slope"))
                    return
                validation = history[["MA_SHORT", "MA_LONG"]].dropna().iloc[
                    -(self.config.pre_cross_validation_sessions + 1):-1
                ]
                if (
                    len(validation) < self.config.pre_cross_validation_sessions
                    or not (validation["MA_SHORT"] < validation["MA_LONG"]).all()
                ):
                    run.failed.append(self._failure(symbol, "Impending Golden Cross Validation", "Short MA was not strictly below Long MA throughout the configured pre-cross validation period"))
                    return
                cross = {
                    "valid": False,
                    "cross_date": None,
                    "days_since_cross": None,
                }
                cross_date = None
                strategy = "Impending Golden Cross"
            reversal = self._long_ma_reversal(history)
            if reversal is None:
                run.failed.append(self._failure(symbol, "Long MA Validation", "Insufficient Long MA history for 52-week high"))
                return
            (
                peak_value,
                peak_date,
                peak_age,
                trough_value,
                trough_date,
                decline_duration,
                decline_percent,
                recovery_slope,
                long_ma_recovering,
            ) = reversal
            if decline_percent < self.config.min_long_ma_decline:
                run.failed.append(self._failure(symbol, "Long MA Validation", "Long MA decline from 52-week high to trough is below configured minimum"))
                return
            if decline_duration < self.config.min_long_ma_decline_duration:
                run.failed.append(self._failure(symbol, "Long MA Validation", "Long MA decline from 52-week high to trough is shorter than configured minimum duration"))
                return
            if is_post_cross:
                if not long_ma_recovering:
                    run.failed.append(self._failure(symbol, "Long MA Validation", "Post-trough 5-session Long MA slope is not positive"))
                    return
            elif latest["MA_LONG"] < trough_value or long_ma_slope < 0:
                run.failed.append(self._failure(symbol, "Impending Golden Cross Validation", "Long MA is below its trough or its latest 5-session slope is negative"))
                return

            if latest["Close"] <= latest["MA_LONG"]:
                run.failed.append(self._failure(symbol, "Price Validation", "Close price is not above Long MA"))
                return
            price_premium = Indicators.distance_from_ma(latest["Close"], latest["MA_LONG"])
            if price_premium > self.config.max_price_premium:
                run.failed.append(self._failure(symbol, "Price Validation", "Close price is too far above Long MA"))
                return
            post_cross_days = (
                len(history.loc[history.index > cross_date]) if is_post_cross else None
            )
            if (
                is_post_cross
                and self.config.require_post_cross_sessions
                and post_cross_days < self.MIN_POST_CROSS_DAYS
            ):
                run.failed.append(self._failure(symbol, "Post-Cross Validation", "Golden Cross needs 10 post-cross sessions", "optional"))
                return

            score_slope = SlopeAnalyzer.calculate_slope(history["MA_LONG"], self.SCORE_SLOPE_LOOKBACK)
            slope_label = SlopeAnalyzer.classify_slope(score_slope)
            fundamentals = self.fundamentals_provider.get_fundamentals(symbol)
            industry_valuation = self.industry_valuation_service.valuation_for(
                fundamentals["industry"]
            )
            score_breakdown = (
                self._score(cross, slope_label, price_premium, fundamentals)
                if is_post_cross
                else {}
            )
            result = ScanResult(
                symbol=symbol, company_name=fundamentals["company_name"], close=round(latest["Close"], 2),
                ma_short=round(latest["MA_SHORT"], 2), ma_long=round(latest["MA_LONG"], 2),
                cross_date=cross_date, days_since_cross=cross["days_since_cross"], distance_from_ma=round(price_premium, 2),
                slope_value=round(score_slope, 4), slope_label=slope_label,
                short_ma_rising=True, short_ma_slope=round(short_ma_slope, 4), long_ma_52_week_peak=round(peak_value, 2),
                long_ma_peak_date=peak_date, long_ma_peak_age=peak_age,
                long_ma_trough=round(trough_value, 2), long_ma_trough_date=trough_date,
                long_ma_decline_duration=decline_duration,
                long_ma_decline_percent=round(decline_percent, 2),
                long_ma_recovery_slope=(
                    round(recovery_slope, 4)
                    if recovery_slope is not None
                    else None
                ),
                long_ma_slope=round(long_ma_slope, 4),
                price_above_long_ma_percent=round(price_premium, 2),
                strategy=strategy,
                impending_gap_percent=(
                    round(gap_percent, 2) if not is_post_cross else None
                ),
                pre_cross_validation_sessions=(
                    self.config.pre_cross_validation_sessions
                    if not is_post_cross
                    else None
                ),
                market_cap=fundamentals["market_cap"], pe=fundamentals["pe"],
                pe_source=fundamentals.get("pe_source"),
                eps=fundamentals["eps"], sector=fundamentals["sector"], industry=fundamentals["industry"],
                **industry_valuation,
                score=sum(score_breakdown.values()),
                **score_breakdown,
            )
            if is_post_cross:
                run.passed.append(result)
            else:
                run.impending.append(result)
        except Exception:
            logger.exception("Unexpected scan failure for %s", symbol)
            run.failed.append(self._failure(symbol, "Processing", "Unexpected error while evaluating the symbol"))
