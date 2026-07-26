"""Evaluation of selected fundamental filters with lenient missing data."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from models.optional_filter import (
    DEBT_TO_EQUITY,
    EPS_GROWTH,
    HISTORICAL_STOCK_PE,
    MARKET_CAP,
    PEG_RATIO,
    PROFIT_GROWTH,
    RELATIVE_INDUSTRY_PE,
    RETURN_ON_EQUITY,
    SALES_GROWTH,
    OptionalFilterConfig,
)


FILTER_LABELS = {
    RELATIVE_INDUSTRY_PE: "Relative Industry P/E",
    HISTORICAL_STOCK_PE: "P/E vs. Historical Stock P/E",
    PEG_RATIO: "PEG Ratio",
    PROFIT_GROWTH: "Profit Growth",
    EPS_GROWTH: "EPS Growth",
    SALES_GROWTH: "Sales / Revenue Growth",
    RETURN_ON_EQUITY: "Return on Equity (ROE)",
    DEBT_TO_EQUITY: "Debt-to-Equity (D/E) Ratio",
    MARKET_CAP: "Market Capitalisation",
}


class EvaluationStatus(str, Enum):
    """The three outcomes supported by an optional filter."""

    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class FilterEvaluation:
    """Auditable outcome for one stock and selected filter."""

    key: str
    label: str
    status: EvaluationStatus
    reason: str


def _number(value, *, positive: bool = False, non_negative: bool = False):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if positive and number <= 0:
        return None
    if non_negative and number < 0:
        return None
    return number


def _is_financial_company(fundamentals: dict) -> bool:
    classification = " ".join(
        str(fundamentals.get(field) or "").lower()
        for field in ("sector", "industry")
    )
    financial_terms = (
        "bank",
        "financial",
        "insurance",
        "credit service",
        "capital market",
        "asset management",
        "mortgage",
    )
    return any(term in classification for term in financial_terms)


class FundamentalFilterEvaluator:
    """Evaluate filters without treating unavailable fields as pass or fail."""

    def evaluate(
        self,
        selected: tuple[OptionalFilterConfig, ...],
        fundamentals: dict,
        industry_valuation: dict,
        screener: dict,
    ) -> list[FilterEvaluation]:
        return [
            self._evaluate_one(config, fundamentals, industry_valuation, screener)
            for config in selected
        ]

    @staticmethod
    def _result(
        config: OptionalFilterConfig,
        status: EvaluationStatus,
        reason: str,
    ) -> FilterEvaluation:
        return FilterEvaluation(
            key=config.key,
            label=FILTER_LABELS[config.key],
            status=status,
            reason=reason,
        )

    def _evaluate_one(
        self,
        config: OptionalFilterConfig,
        fundamentals: dict,
        industry_valuation: dict,
        screener: dict,
    ) -> FilterEvaluation:
        if config.key == RELATIVE_INDUSTRY_PE:
            return self._relative_industry_pe(
                config, fundamentals, industry_valuation
            )
        if config.key == HISTORICAL_STOCK_PE:
            return self._historical_stock_pe(config, fundamentals, screener)
        if config.key == PEG_RATIO:
            return self._peg(config, fundamentals, screener)
        if config.key in {PROFIT_GROWTH, EPS_GROWTH, SALES_GROWTH}:
            return self._growth(config, screener)
        if config.key == RETURN_ON_EQUITY:
            return self._minimum(config, screener.get("roe"), "ROE", "%")
        if config.key == DEBT_TO_EQUITY:
            if _is_financial_company(fundamentals):
                return self._result(
                    config,
                    EvaluationStatus.PASS,
                    "Debt-to-equity is not applied to banks or financial companies",
                )
            return self._maximum(
                config,
                screener.get("debt_to_equity"),
                "Debt-to-equity",
                non_negative=True,
            )
        if config.key == MARKET_CAP:
            return self._market_cap(config, fundamentals)
        raise ValueError(f"Unsupported optional filter: {config.key}")

    def _relative_industry_pe(
        self,
        config: OptionalFilterConfig,
        fundamentals: dict,
        industry_valuation: dict,
    ) -> FilterEvaluation:
        stock_pe = _number(fundamentals.get("pe"), positive=True)
        industry_pe = _number(
            industry_valuation.get("industry_median_pe"), positive=True
        )
        if stock_pe is None or industry_pe is None:
            return self._result(
                config,
                EvaluationStatus.NOT_EVALUATED,
                "Current stock or median Industry P/E is unavailable",
            )
        if stock_pe < industry_pe:
            return self._result(
                config,
                EvaluationStatus.PASS,
                f"Stock P/E {stock_pe:.2f} is below median Industry P/E {industry_pe:.2f}",
            )
        return self._result(
            config,
            EvaluationStatus.FAIL,
            f"Stock P/E {stock_pe:.2f} is not below median Industry P/E {industry_pe:.2f}",
        )

    def _historical_stock_pe(
        self,
        config: OptionalFilterConfig,
        fundamentals: dict,
        screener: dict,
    ) -> FilterEvaluation:
        stock_pe = _number(fundamentals.get("pe"), positive=True)
        benchmarks = [
            (years, _number(screener.get(f"pe_average_{years}y"), positive=True))
            for years in (3, 5, 10)
        ]
        available = [(years, value) for years, value in benchmarks if value is not None]
        if stock_pe is None or not available:
            return self._result(
                config,
                EvaluationStatus.NOT_EVALUATED,
                "Current or historical stock P/E data is unavailable",
            )
        failures = [
            f"{years}Y average {value:.2f}"
            for years, value in available
            if stock_pe >= value
        ]
        if failures:
            return self._result(
                config,
                EvaluationStatus.FAIL,
                f"Current P/E {stock_pe:.2f} is not below " + ", ".join(failures),
            )
        return self._result(
            config,
            EvaluationStatus.PASS,
            f"Current P/E {stock_pe:.2f} is below all available historical averages",
        )

    def _peg(
        self,
        config: OptionalFilterConfig,
        fundamentals: dict,
        screener: dict,
    ) -> FilterEvaluation:
        stock_pe = _number(fundamentals.get("pe"), positive=True)
        profit_growth = _number(
            screener.get("profit_growth_3y"), positive=True
        )
        if stock_pe is None or profit_growth is None:
            return self._result(
                config,
                EvaluationStatus.NOT_EVALUATED,
                "Current P/E or 3-year profit growth is unavailable",
            )
        peg = stock_pe / profit_growth
        if peg <= config.threshold:
            return self._result(
                config,
                EvaluationStatus.PASS,
                f"PEG {peg:.2f} is within the maximum {config.threshold:.2f}",
            )
        return self._result(
            config,
            EvaluationStatus.FAIL,
            f"PEG {peg:.2f} exceeds the maximum {config.threshold:.2f}",
        )

    def _growth(
        self,
        config: OptionalFilterConfig,
        screener: dict,
    ) -> FilterEvaluation:
        prefix = {
            PROFIT_GROWTH: "profit_growth",
            EPS_GROWTH: "eps_growth",
            SALES_GROWTH: "sales_growth",
        }[config.key]
        available = [
            (years, value)
            for years in (3, 5, 10)
            if (value := _number(screener.get(f"{prefix}_{years}y"))) is not None
        ]
        if not available:
            return self._result(
                config,
                EvaluationStatus.NOT_EVALUATED,
                f"{FILTER_LABELS[config.key]} data is unavailable",
            )
        failures = [
            f"{years}Y {value:.2f}%"
            for years, value in available
            if value <= config.threshold
        ]
        if failures:
            return self._result(
                config,
                EvaluationStatus.FAIL,
                f"{FILTER_LABELS[config.key]} does not exceed "
                f"{config.threshold:.2f}% for " + ", ".join(failures),
            )
        return self._result(
            config,
            EvaluationStatus.PASS,
            f"All available periods exceed {config.threshold:.2f}%",
        )

    def _minimum(
        self,
        config: OptionalFilterConfig,
        raw_value,
        metric: str,
        unit: str = "",
    ) -> FilterEvaluation:
        value = _number(raw_value)
        if value is None:
            return self._result(
                config,
                EvaluationStatus.NOT_EVALUATED,
                f"{metric} data is unavailable",
            )
        if value >= config.threshold:
            return self._result(
                config,
                EvaluationStatus.PASS,
                f"{metric} {value:.2f}{unit} meets the minimum {config.threshold:.2f}{unit}",
            )
        return self._result(
            config,
            EvaluationStatus.FAIL,
            f"{metric} {value:.2f}{unit} is below the minimum {config.threshold:.2f}{unit}",
        )

    def _maximum(
        self,
        config: OptionalFilterConfig,
        raw_value,
        metric: str,
        *,
        non_negative: bool = False,
    ) -> FilterEvaluation:
        value = _number(raw_value, non_negative=non_negative)
        if value is None:
            return self._result(
                config,
                EvaluationStatus.NOT_EVALUATED,
                f"{metric} data is unavailable",
            )
        if value <= config.threshold:
            return self._result(
                config,
                EvaluationStatus.PASS,
                f"{metric} {value:.2f} is within the maximum {config.threshold:.2f}",
            )
        return self._result(
            config,
            EvaluationStatus.FAIL,
            f"{metric} {value:.2f} exceeds the maximum {config.threshold:.2f}",
        )

    def _market_cap(
        self,
        config: OptionalFilterConfig,
        fundamentals: dict,
    ) -> FilterEvaluation:
        market_cap = _number(fundamentals.get("market_cap"), positive=True)
        if market_cap is None:
            return self._result(
                config,
                EvaluationStatus.NOT_EVALUATED,
                "Market-cap data is unavailable",
            )
        crore = market_cap / 10_000_000
        bucket_matches = {
            "large": crore > 20_000,
            "mid": 5_000 <= crore <= 20_000,
            "small": 500 <= crore < 5_000,
            "micro": crore < 500,
        }
        matches_bucket = any(
            bucket_matches[bucket] for bucket in config.market_cap_buckets
        )
        matches_custom = (
            (config.custom_min_crore is not None or config.custom_max_crore is not None)
            and (
                config.custom_min_crore is None
                or crore >= config.custom_min_crore
            )
            and (
                config.custom_max_crore is None
                or crore <= config.custom_max_crore
            )
        )
        if matches_bucket or matches_custom:
            return self._result(
                config,
                EvaluationStatus.PASS,
                f"Market cap ₹{crore:,.0f} Cr matches the selected range",
            )
        return self._result(
            config,
            EvaluationStatus.FAIL,
            f"Market cap ₹{crore:,.0f} Cr is outside the selected range",
        )
