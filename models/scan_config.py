"""Typed configuration for one scanner run."""

from dataclasses import dataclass

from models.optional_filter import OptionalFilterConfig, SCREENER_OPTIONAL_FILTERS


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
    optional_filters: tuple[OptionalFilterConfig, ...] = ()
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
        selected_keys = [optional_filter.key for optional_filter in self.optional_filters]
        if len(selected_keys) != len(set(selected_keys)):
            raise ValueError("An optional filter cannot be selected more than once")
        for optional_filter in self.optional_filters:
            optional_filter.validate()

    @property
    def optional_checks_selected(self) -> bool:
        return bool(self.optional_filters)

    @property
    def requires_screener_data(self) -> bool:
        """Return whether any selected filter reads the committed Screener snapshot."""
        return any(
            optional_filter.key in SCREENER_OPTIONAL_FILTERS
            for optional_filter in self.optional_filters
        )
