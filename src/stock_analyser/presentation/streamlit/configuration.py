"""Translate presentation settings into validated domain configuration."""

from stock_analyser.domain.scanning.models import OptionalFilterConfig, ScanConfig


def build_scan_config(settings: dict) -> ScanConfig:
    return ScanConfig(
        short_ma=settings["short_ma"],
        long_ma=settings["long_ma"],
        max_cross_age=settings["cross_age"],
        min_long_ma_decline_duration=settings["min_long_ma_decline_duration"],
        min_long_ma_decline=settings["min_long_ma_decline"],
        max_price_premium=settings["max_price_premium"],
        include_impending_crosses=settings["include_impending_crosses"],
        impending_max_gap_pct=settings["impending_max_gap_pct"],
        pre_cross_validation_sessions=settings["pre_cross_validation_sessions"],
        optional_filters=tuple(
            OptionalFilterConfig.from_dict(values)
            for values in settings.get("optional_filters", ())
        ),
        adjusted_prices=settings["adjusted_prices"],
    )


def build_backtest_config(settings: dict | None) -> ScanConfig:
    values = settings or {}
    return ScanConfig(
        values.get("short_ma", 50),
        values.get("long_ma", 200),
        values.get("cross_age", 80),
        values.get("min_long_ma_decline_duration", 60),
        values.get("min_long_ma_decline", 10),
        values.get("max_price_premium", 10),
        adjusted_prices=False,
    )


__all__ = ["build_backtest_config", "build_scan_config"]
