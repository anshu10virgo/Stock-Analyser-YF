"""Return horizons expressed in trading sessions."""

HORIZON_SESSIONS = {
    "1W": 5,
    "2W": 10,
    "3W": 15,
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
}

__all__ = ["HORIZON_SESSIONS"]
