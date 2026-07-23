"""Typed configuration for one scanner run."""

from dataclasses import dataclass


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
    impending_max_gap_pct: float = 3
    pre_cross_validation_sessions: int = 20
    require_post_cross_sessions: bool = False
    adjusted_prices: bool = False

    def validate(self) -> None:
        """Fail fast for configuration combinations that cannot be evaluated."""
        if self.short_ma >= self.long_ma:
            raise ValueError("Short-term moving average must be below long-term moving average")
        if self.max_cross_age < 1 or self.min_long_ma_decline_duration < 1:
            raise ValueError("Golden Cross age and Long MA decline duration must be positive")
        if self.pre_cross_validation_sessions < 1:
            raise ValueError("Pre-cross validation period must be positive")
        if (
            self.min_long_ma_decline < 0
            or self.max_price_premium < 0
            or self.impending_max_gap_pct < 0
        ):
            raise ValueError("Percentage thresholds cannot be negative")

    @property
    def optional_checks_selected(self) -> bool:
        return self.require_post_cross_sessions
