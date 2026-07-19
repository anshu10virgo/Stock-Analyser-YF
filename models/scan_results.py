"""Typed qualified-stock record used by the scan service and UI."""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional


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
        """Return the stable UI/dataframe contract."""
        values = asdict(self)
        values["slope"] = values.pop("slope_value")
        values.pop("status")
        values.pop("failure_reason")
        return values
