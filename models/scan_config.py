"""Typed configuration for one scanner run."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScanConfig:
    """All rules and price settings applied consistently in one scan."""

    short_ma: int
    long_ma: int
    max_cross_age: int
    pre_cross_days: int
    slope_lookback: int
    max_distance: float
    require_pre_cross_trough: bool = False
    require_pre_cross_decline: bool = False
    require_post_cross_sessions: bool = False
    require_post_cross_increase: bool = False
    adjusted_prices: bool = False

    def validate(self) -> None:
        """Fail fast for configuration combinations that cannot be evaluated."""
        if self.short_ma >= self.long_ma:
            raise ValueError("Short-term moving average must be below long-term moving average")
        if self.pre_cross_days < 1 or self.slope_lookback < 2:
            raise ValueError("Lookback settings must be positive")
        if self.max_distance < 0:
            raise ValueError("Maximum price distance cannot be negative")

    @property
    def optional_checks_selected(self) -> bool:
        return any(
            (
                self.require_pre_cross_trough,
                self.require_pre_cross_decline,
                self.require_post_cross_sessions,
                self.require_post_cross_increase,
            )
        )
