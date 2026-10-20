"""Application service for configured stock scans."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Iterable
from datetime import datetime

from stock_analyser.domain.scanning.impending_cross_rules import (
    evaluate_impending_cross,
)
from stock_analyser.domain.scanning.indicators import (
    Indicators,
    SlopeAnalyzer,
    validate_price,
    validate_short_ma_slope,
)
from stock_analyser.domain.scanning.models import (
    FailureResult,
    ScanConfig,
    ScanResult,
    ScanRun,
)
from stock_analyser.domain.scanning.optional_rules import (
    EvaluationStatus,
    FundamentalFilterEvaluator,
)
from stock_analyser.domain.scanning.post_cross_rules import evaluate_post_cross
from stock_analyser.domain.scanning.reversal_rules import (
    evaluate_long_ma_reversal,
    validate_long_ma_reversal,
)
from stock_analyser.domain.scanning.scoring import ScoringEngine


logger = logging.getLogger(__name__)


class ScanService:
    """Coordinates market data, technical rules, fundamentals, and ranking."""

    SHORT_MA_SLOPE_SESSIONS = 5
    LONG_MA_52_WEEK_SESSIONS = 252
    LONG_MA_RECOVERY_SLOPE_SESSIONS = 5
    SCORE_SLOPE_LOOKBACK = 20
    HISTORY_SAFETY_SESSIONS = 50
    CONSERVATIVE_TRADING_SESSIONS_PER_YEAR = 230

    def __init__(
        self,
        config: ScanConfig,
        data_provider=None,
        fundamentals_provider=None,
        industry_valuation_service=None,
        screener_provider=None,
        fundamental_filter_evaluator=None,
    ):
        config.validate()
        if data_provider is None:
            raise ValueError("A market-data provider is required")
        if fundamentals_provider is None:
            raise ValueError("A fundamentals provider is required")
        if industry_valuation_service is None:
            raise ValueError("An industry-valuation provider is required")
        self.config = config
        self.data_provider = data_provider
        self.fundamentals_provider = fundamentals_provider
        self.industry_valuation_service = industry_valuation_service
        self.screener_provider = screener_provider
        self.fundamental_filter_evaluator = (
            fundamental_filter_evaluator or FundamentalFilterEvaluator()
        )
        self._screener_records = {}
        self._optional_filter_metrics = {}

    @staticmethod
    def _failure(symbol, stage, reason, check_type="mandatory"):
        return FailureResult(symbol, stage, reason, check_type)

    def _long_ma_reversal(self, history):
        """Compatibility facade for legacy Backtester and report callers."""
        reversal = evaluate_long_ma_reversal(
            history,
            high_window_sessions=self.LONG_MA_52_WEEK_SESSIONS,
            recovery_slope_sessions=self.LONG_MA_RECOVERY_SLOPE_SESSIONS,
        )
        return reversal.as_tuple() if reversal is not None else None

    def _score(self, cross, slope_label, distance, fundamentals):
        return ScoringEngine.score_breakdown(
            cross["days_since_cross"],
            slope_label,
            distance,
            fundamentals,
        )

    def _prepare_optional_filters(self, symbols: list[str]) -> None:
        """Load selected filter data once and initialise audit counters."""
        self._optional_filter_metrics = {
            optional_filter.key: {
                EvaluationStatus.PASS.value: 0,
                EvaluationStatus.FAIL.value: 0,
                EvaluationStatus.NOT_EVALUATED.value: 0,
            }
            for optional_filter in self.config.optional_filters
        }
        self._screener_records = {}
        if (
            not symbols
            or not self.config.requires_screener_data
            or self.screener_provider is None
        ):
            return
        try:
            self._screener_records = self.screener_provider.fundamental_metrics_batch(
                symbols
            )
        except Exception:
            logger.exception(
                "Committed Screener summary is unavailable for optional filters"
            )

    def _evaluate_optional_filters(
        self,
        symbol: str,
        fundamentals: dict,
        industry_valuation: dict,
        run: ScanRun,
    ) -> list[str] | None:
        """Return unavailable labels, or reject and return ``None`` on failure."""
        evaluations = self.fundamental_filter_evaluator.evaluate(
            self.config.optional_filters,
            fundamentals,
            industry_valuation,
            self._screener_records.get(symbol, {}),
        )
        for evaluation in evaluations:
            self._optional_filter_metrics[evaluation.key][
                evaluation.status.value
            ] += 1
        failed = next(
            (
                evaluation
                for evaluation in evaluations
                if evaluation.status == EvaluationStatus.FAIL
            ),
            None,
        )
        if failed is not None:
            run.failed.append(
                self._failure(
                    symbol,
                    f"Optional Fundamentals — {failed.label}",
                    failed.reason,
                    "optional",
                )
            )
            return None
        return [
            evaluation.label
            for evaluation in evaluations
            if evaluation.status == EvaluationStatus.NOT_EVALUATED
        ]

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
        self._prepare_optional_filters(symbols)
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
            run.metrics["optional_filters"] = self._optional_filter_metrics
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
        run.metrics["optional_filters"] = self._optional_filter_metrics
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
            failure = validate_short_ma_slope(short_ma_slope)
            if failure is not None:
                run.failed.append(self._failure(symbol, failure.stage, failure.reason))
                return

            is_post_cross = latest["MA_SHORT"] > latest["MA_LONG"]
            if is_post_cross:
                setup, failure = evaluate_post_cross(
                    history,
                    self.config.max_cross_age,
                    datetime.today().date(),
                )
            elif not self.config.include_impending_crosses:
                setup, failure = None, None
                run.failed.append(
                    self._failure(
                        symbol,
                        "Post Golden Cross Validation",
                        "Short MA is not above Long MA",
                    )
                )
                return
            else:
                setup, failure = evaluate_impending_cross(
                    history,
                    short_ma_slope=short_ma_slope,
                    long_ma_slope=long_ma_slope,
                    maximum_gap_percent=self.config.impending_max_gap_pct,
                    validation_sessions=self.config.pre_cross_validation_sessions,
                )
            if failure is not None:
                run.failed.append(self._failure(symbol, failure.stage, failure.reason))
                return

            reversal_result = evaluate_long_ma_reversal(
                history,
                high_window_sessions=self.LONG_MA_52_WEEK_SESSIONS,
                recovery_slope_sessions=self.LONG_MA_RECOVERY_SLOPE_SESSIONS,
            )
            failure = validate_long_ma_reversal(
                reversal_result,
                is_post_cross=setup.is_post_cross,
                current_long_ma=latest["MA_LONG"],
                latest_long_ma_slope=long_ma_slope,
                minimum_decline_percent=self.config.min_long_ma_decline,
                minimum_decline_duration=self.config.min_long_ma_decline_duration,
            )
            if failure is not None:
                run.failed.append(self._failure(symbol, failure.stage, failure.reason))
                return

            price_premium, failure = validate_price(
                latest, self.config.max_price_premium
            )
            if failure is not None:
                run.failed.append(self._failure(symbol, failure.stage, failure.reason))
                return

            cross = setup.cross
            cross_date = setup.cross_date
            strategy = setup.strategy
            gap_percent = setup.gap_percent
            (
                peak_value,
                peak_date,
                peak_age,
                trough_value,
                trough_date,
                decline_duration,
                decline_percent,
                recovery_slope,
                _long_ma_recovering,
            ) = reversal_result.as_tuple()
            score_slope = SlopeAnalyzer.calculate_slope(history["MA_LONG"], self.SCORE_SLOPE_LOOKBACK)
            slope_label = SlopeAnalyzer.classify_slope(score_slope)
            fundamentals = self.fundamentals_provider.get_fundamentals(symbol)
            industry_valuation = self.industry_valuation_service.valuation_for(
                fundamentals["industry"]
            )
            unavailable_optional_filters = self._evaluate_optional_filters(
                symbol,
                fundamentals,
                industry_valuation,
                run,
            )
            if unavailable_optional_filters is None:
                return
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
                optional_filters_not_evaluated=unavailable_optional_filters,
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
