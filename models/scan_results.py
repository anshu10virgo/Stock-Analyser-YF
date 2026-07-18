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

    company_name: Optional[str] = None
    pre_cross_slope: Optional[float] = None
    pre_cross_trough_date: Optional[datetime] = None

    market_cap: Optional[float] = None
    pe: Optional[float] = None
    eps: Optional[float] = None

    sector: Optional[str] = None
    industry: Optional[str] = None

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
