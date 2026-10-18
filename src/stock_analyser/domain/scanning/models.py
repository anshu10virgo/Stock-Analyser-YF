"""Typed configuration and outcomes for the scanning domain."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

import pandas as pd


RELATIVE_INDUSTRY_PE = "relative_industry_pe"
HISTORICAL_STOCK_PE = "historical_stock_pe"
PEG_RATIO = "peg_ratio"
PROFIT_GROWTH = "profit_growth"
EPS_GROWTH = "eps_growth"
SALES_GROWTH = "sales_growth"
RETURN_ON_EQUITY = "return_on_equity"
DEBT_TO_EQUITY = "debt_to_equity"
MARKET_CAP = "market_cap"

SUPPORTED_OPTIONAL_FILTERS = (
    RELATIVE_INDUSTRY_PE,
    HISTORICAL_STOCK_PE,
    PEG_RATIO,
    PROFIT_GROWTH,
    EPS_GROWTH,
    SALES_GROWTH,
    RETURN_ON_EQUITY,
    DEBT_TO_EQUITY,
    MARKET_CAP,
)
SCREENER_OPTIONAL_FILTERS = frozenset(
    {
        HISTORICAL_STOCK_PE,
        PEG_RATIO,
        PROFIT_GROWTH,
        EPS_GROWTH,
        SALES_GROWTH,
        RETURN_ON_EQUITY,
        DEBT_TO_EQUITY,
    }
)
MARKET_CAP_BUCKETS = ("large", "mid", "small", "micro")


@dataclass(frozen=True)
class OptionalFilterConfig:
    """One selected fundamental filter and its user-controlled values."""

    key: str
    threshold: float | None = None
    market_cap_buckets: tuple[str, ...] = ()
    custom_min_crore: float | None = None
    custom_max_crore: float | None = None

    @classmethod
    def from_dict(cls, values: dict) -> "OptionalFilterConfig":
        return cls(
            key=values["key"],
            threshold=values.get("threshold"),
            market_cap_buckets=tuple(values.get("market_cap_buckets", ())),
            custom_min_crore=values.get("custom_min_crore"),
            custom_max_crore=values.get("custom_max_crore"),
        )

    def as_dict(self) -> dict:
        values = asdict(self)
        values["market_cap_buckets"] = list(self.market_cap_buckets)
        return values

    def validate(self) -> None:
        if self.key not in SUPPORTED_OPTIONAL_FILTERS:
            raise ValueError(f"Unsupported optional filter: {self.key}")
        if self.key == PEG_RATIO and (
            self.threshold is None or not 0 <= self.threshold <= 2
        ):
            raise ValueError("PEG threshold must be between 0 and 2")
        if self.key == DEBT_TO_EQUITY and (
            self.threshold is None or not 0 <= self.threshold <= 2
        ):
            raise ValueError("Debt-to-equity threshold must be between 0 and 2")
        if self.key in {
            PROFIT_GROWTH,
            EPS_GROWTH,
            SALES_GROWTH,
            RETURN_ON_EQUITY,
        } and (self.threshold is None or not 0 <= self.threshold <= 50):
            raise ValueError(f"{self.key} threshold must be between 0 and 50")
        unknown_buckets = set(self.market_cap_buckets) - set(MARKET_CAP_BUCKETS)
        if unknown_buckets:
            raise ValueError(
                f"Unsupported market-cap buckets: {sorted(unknown_buckets)}"
            )
        if self.custom_min_crore is not None and self.custom_min_crore < 0:
            raise ValueError("Custom market-cap minimum cannot be negative")
        if self.custom_max_crore is not None and self.custom_max_crore < 0:
            raise ValueError("Custom market-cap maximum cannot be negative")
        if (
            self.custom_min_crore is not None
            and self.custom_max_crore is not None
            and self.custom_min_crore > self.custom_max_crore
        ):
            raise ValueError("Custom market-cap minimum cannot exceed its maximum")
        if (
            self.key == MARKET_CAP
            and not self.market_cap_buckets
            and self.custom_min_crore is None
            and self.custom_max_crore is None
        ):
            raise ValueError("Market-cap filter requires a bucket or custom boundary")


@dataclass(frozen=True)
class ScanConfig:
    """All rules and price settings applied consistently in one scan."""

    short_ma: int
    long_ma: int
    max_cross_age: int
    min_long_ma_decline_duration: int
    min_long_ma_decline: float
    max_price_premium: float
    include_impending_crosses: bool = False
    impending_max_gap_pct: float = 10
    pre_cross_validation_sessions: int = 20
    optional_filters: tuple[OptionalFilterConfig, ...] = ()
    adjusted_prices: bool = False

    def validate(self) -> None:
        if self.short_ma >= self.long_ma:
            raise ValueError(
                "Short-term moving average must be below long-term moving average"
            )
        if self.max_cross_age < 1 or self.min_long_ma_decline_duration < 1:
            raise ValueError(
                "Golden Cross age and Long MA decline duration must be positive"
            )
        if self.pre_cross_validation_sessions < 1:
            raise ValueError("Pre-cross validation period must be positive")
        if (
            self.min_long_ma_decline < 0
            or self.max_price_premium < 0
            or self.impending_max_gap_pct < 0
        ):
            raise ValueError("Percentage thresholds cannot be negative")
        selected_keys = [item.key for item in self.optional_filters]
        if len(selected_keys) != len(set(selected_keys)):
            raise ValueError("An optional filter cannot be selected more than once")
        for optional_filter in self.optional_filters:
            optional_filter.validate()

    @property
    def optional_checks_selected(self) -> bool:
        return bool(self.optional_filters)

    @property
    def requires_screener_data(self) -> bool:
        return any(
            optional_filter.key in SCREENER_OPTIONAL_FILTERS
            for optional_filter in self.optional_filters
        )


@dataclass
class FailureResult:
    symbol: str
    stage: str
    reason: str
    check_type: str = "mandatory"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    symbol: str
    close: float
    ma_short: float
    ma_long: float
    cross_date: Optional[datetime]
    days_since_cross: Optional[int]
    distance_from_ma: float
    slope_value: float
    slope_label: str
    short_ma_rising: bool = False
    short_ma_slope: Optional[float] = None
    long_ma_52_week_peak: Optional[float] = None
    long_ma_peak_date: Optional[datetime] = None
    long_ma_peak_age: Optional[int] = None
    long_ma_trough: Optional[float] = None
    long_ma_trough_date: Optional[datetime] = None
    long_ma_decline_duration: Optional[int] = None
    long_ma_decline_percent: Optional[float] = None
    long_ma_recovery_slope: Optional[float] = None
    price_above_long_ma_percent: Optional[float] = None
    strategy: str = "Post Golden Cross"
    long_ma_slope: Optional[float] = None
    impending_gap_percent: Optional[float] = None
    pre_cross_validation_sessions: Optional[int] = None
    company_name: Optional[str] = None
    market_cap: Optional[float] = None
    pe: Optional[float] = None
    pe_source: Optional[str] = None
    eps: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    industry_weighted_pe: Optional[float] = None
    industry_median_pe: Optional[float] = None
    industry_peer_count: int = 0
    optional_filters_not_evaluated: list[str] = field(default_factory=list)
    score: float = 0
    score_cross: int = 0
    score_slope: int = 0
    score_distance: int = 0
    score_pe: int = 0
    score_eps: int = 0
    score_market_cap: int = 0
    status: str = "PASS"
    failure_reason: str = ""

    def as_dict(self) -> dict:
        values = asdict(self)
        values["slope"] = values.pop("slope_value")
        values.pop("status")
        values.pop("failure_reason")
        return values


@dataclass
class ScanRun:
    """Qualified and rejected symbols from one requested universe."""

    passed: list[ScanResult] = field(default_factory=list)
    impending: list[ScanResult] = field(default_factory=list)
    failed: list[FailureResult] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def as_dataframes(self) -> dict[str, pd.DataFrame]:
        passed_df = pd.DataFrame([record.as_dict() for record in self.passed])
        impending_df = pd.DataFrame([record.as_dict() for record in self.impending])
        failed_df = pd.DataFrame([record.as_dict() for record in self.failed])
        if not passed_df.empty:
            passed_df.sort_values(by="score", ascending=False, inplace=True)
            passed_df.reset_index(drop=True, inplace=True)
        if not impending_df.empty:
            impending_df.sort_values(
                by=["impending_gap_percent", "short_ma_slope"],
                ascending=[True, False],
                inplace=True,
            )
            impending_df.reset_index(drop=True, inplace=True)
        return {
            "passed": passed_df,
            "impending": impending_df,
            "failed": failed_df,
        }


@dataclass(frozen=True)
class RuleFailure:
    stage: str
    reason: str


@dataclass(frozen=True)
class CrossSetup:
    strategy: str
    is_post_cross: bool
    cross: dict[str, Any]
    cross_date: pd.Timestamp | None
    gap_percent: float | None = None


@dataclass(frozen=True)
class LongMaReversal:
    peak_value: float
    peak_date: pd.Timestamp
    peak_age: int
    trough_value: float
    trough_date: pd.Timestamp
    decline_duration: int
    decline_percent: float
    recovery_slope: float | None
    recovering: bool

    def as_tuple(self) -> tuple:
        return (
            self.peak_value,
            self.peak_date,
            self.peak_age,
            self.trough_value,
            self.trough_date,
            self.decline_duration,
            self.decline_percent,
            self.recovery_slope,
            self.recovering,
        )
