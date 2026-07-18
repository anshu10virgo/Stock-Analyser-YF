from dataclasses import dataclass
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

    market_cap: Optional[float] = None
    pe: Optional[float] = None
    eps: Optional[float] = None

    sector: Optional[str] = None
    industry: Optional[str] = None

    score: float = 0

    status: str = "PASS"

    failure_reason: str = ""
