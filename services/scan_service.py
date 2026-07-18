"""Application service for configured stock scans."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from core.data_loader import DataLoader
from core.fundamentals import Fundamentals
from core.golden_cross import GoldenCrossDetector
from core.indicators import Indicators
from core.scoring import ScoringEngine
from core.slope_analyzer import SlopeAnalyzer
from core.trough_detector import TroughDetector
from models.failure_result import FailureResult
from models.scan_config import ScanConfig
from models.scan_results import ScanResult
from models.scan_run import ScanRun
from services.industry_valuation import IndustryValuationService


logger = logging.getLogger(__name__)


class ScanService:
    """Coordinates market data, technical rules, fundamentals, and ranking."""

    MIN_POST_CROSS_DAYS = 10

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

    def _find_pre_cross_trough(self, history, cross_date):
        position = history.index.get_loc(cross_date)
        window = history.iloc[max(0, position - self.config.pre_cross_days):position + 1]
        dates = [date for date in TroughDetector.detect_troughs(window)["dates"] if date < cross_date]
        return dates[-1] if dates else None

    def _long_ma_slopes(self, history, cross_date):
        position = history.index.get_loc(cross_date)
        pre_ma = history.iloc[max(0, position - self.config.slope_lookback):position]["MA_LONG"]
        post_ma = history.iloc[position + 1:]["MA_LONG"]
        pre_slope = None
        post_slope = None
        if len(pre_ma) >= self.config.slope_lookback:
            pre_slope = SlopeAnalyzer.calculate_slope(pre_ma, self.config.slope_lookback)
        if len(post_ma) >= 2:
            post_slope = SlopeAnalyzer.calculate_slope(post_ma, len(post_ma))
        return pre_slope, post_slope, len(post_ma)

    def _optional_failure(self, symbol, history, cross_date):
        trough_date = None
        if self.config.require_pre_cross_trough:
            trough_date = self._find_pre_cross_trough(history, cross_date)
            if trough_date is None:
                return None, None, None, self._failure(symbol, "Trough Validation", "No trough found before Golden Cross", "optional")

        pre_slope, post_slope, post_days = self._long_ma_slopes(history, cross_date)
        if self.config.require_pre_cross_decline:
            if pre_slope is None:
                return None, None, trough_date, self._failure(symbol, "Slope Validation", "Insufficient history for pre-cross MA slope", "optional")
            if pre_slope >= 0:
                return None, None, trough_date, self._failure(symbol, "Slope Validation", "Long MA was not declining before Golden Cross", "optional")
        if self.config.require_post_cross_sessions and post_days < self.MIN_POST_CROSS_DAYS:
            return None, None, trough_date, self._failure(symbol, "Slope Validation", "Golden Cross needs 10 post-cross sessions", "optional")
        if self.config.require_post_cross_increase:
            if post_slope is None:
                return None, None, trough_date, self._failure(symbol, "Slope Validation", "Insufficient post-cross history for MA slope", "optional")
            if post_slope <= 0:
                return None, None, trough_date, self._failure(symbol, "Slope Validation", "Long MA is not increasing after Golden Cross", "optional")
        return pre_slope, post_slope, trough_date, None

    def _score(self, cross, slope_label, distance, fundamentals):
        return ScoringEngine.score_breakdown(
            cross["days_since_cross"],
            slope_label,
            distance,
            fundamentals,
        )

    def scan(self, symbols: Iterable[str], progress_callback: Callable[[int, int], None] | None = None) -> ScanRun:
        symbols = list(symbols)
        run = ScanRun()
        if hasattr(self.industry_valuation_service, "begin_scan"):
            self.industry_valuation_service.begin_scan()
        if not symbols:
            return run
        try:
            batch_data = self.data_provider.download_batch(symbols, adjusted_prices=self.config.adjusted_prices)
            if hasattr(self.data_provider, "market_data_metrics"):
                run.metrics["market_data"] = self.data_provider.market_data_metrics()
        except Exception:
            logger.exception("Batch market-data download failed")
            run.failed.extend(self._failure(symbol, "Market Data", "Unable to download market data for this scan") for symbol in symbols)
            if hasattr(self.data_provider, "market_data_metrics"):
                run.metrics["market_data"] = self.data_provider.market_data_metrics()
            if hasattr(self.industry_valuation_service, "metrics"):
                run.metrics["industry_valuations"] = self.industry_valuation_service.metrics()
            return run
        for index, symbol in enumerate(symbols, start=1):
            if progress_callback:
                progress_callback(index, len(symbols))
            self._scan_symbol(batch_data, symbol, run)
        if hasattr(self.industry_valuation_service, "metrics"):
            run.metrics["industry_valuations"] = self.industry_valuation_service.metrics()
        return run

    def _scan_symbol(self, batch_data, symbol, run):
        try:
            history = self.data_provider.get_symbol_history(batch_data, symbol)
            if history.empty:
                run.failed.append(self._failure(symbol, "Market Data", "No complete market data was returned for the symbol"))
                return
            history = Indicators.add_moving_averages(history, self.config.short_ma, self.config.long_ma)
            cross = GoldenCrossDetector.find_cross(history, self.config.max_cross_age, self.config.pre_cross_days)
            if not cross["valid"]:
                run.failed.append(self._failure(symbol, "Golden Cross Validation", "Golden Cross validation failed"))
                return
            latest = history.iloc[-1]
            cross_date = cross["cross_date"]
            if latest["Close"] < history.loc[cross_date, "Close"]:
                run.failed.append(self._failure(symbol, "Price Validation", "Close price is below Golden Cross close"))
                return
            if latest["Close"] < latest["MA_SHORT"]:
                run.failed.append(self._failure(symbol, "Price Validation", "Close price is below Short MA"))
                return
            if latest["MA_SHORT"] < latest["MA_LONG"]:
                run.failed.append(self._failure(symbol, "Golden Cross Validation", "Golden Cross has been invalidated by a Death Cross"))
                return
            pre_slope, post_slope, trough_date, failure = self._optional_failure(symbol, history, cross_date)
            if failure:
                run.failed.append(failure)
                return
            distance = Indicators.distance_from_ma(latest["Close"], latest["MA_LONG"])
            if abs(distance) > self.config.max_distance:
                run.failed.append(self._failure(symbol, "Price Validation", "Close price is too far from Long MA"))
                return
            score_slope = post_slope if post_slope is not None else SlopeAnalyzer.calculate_slope(history["MA_LONG"], self.config.slope_lookback)
            slope_label = SlopeAnalyzer.classify_slope(score_slope)
            fundamentals = self.fundamentals_provider.get_fundamentals(symbol)
            industry_valuation = self.industry_valuation_service.valuation_for(
                fundamentals["industry"]
            )
            score_breakdown = self._score(cross, slope_label, distance, fundamentals)
            run.passed.append(ScanResult(
                symbol=symbol, company_name=fundamentals["company_name"], close=round(latest["Close"], 2),
                ma_short=round(latest["MA_SHORT"], 2), ma_long=round(latest["MA_LONG"], 2),
                cross_date=cross_date, days_since_cross=cross["days_since_cross"], distance_from_ma=round(distance, 2),
                slope_value=round(score_slope, 4), slope_label=slope_label,
                pre_cross_slope=round(pre_slope, 4) if pre_slope is not None else None,
                pre_cross_trough_date=trough_date, market_cap=fundamentals["market_cap"], pe=fundamentals["pe"],
                eps=fundamentals["eps"], sector=fundamentals["sector"], industry=fundamentals["industry"],
                **industry_valuation,
                score=sum(score_breakdown.values()),
                **score_breakdown,
            ))
        except Exception:
            logger.exception("Unexpected scan failure for %s", symbol)
            run.failed.append(self._failure(symbol, "Processing", "Unexpected error while evaluating the symbol"))
