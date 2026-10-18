"""Pure rules unique to an Impending Golden Cross setup."""

from __future__ import annotations

import pandas as pd

from stock_analyser.domain.scanning.models import CrossSetup, RuleFailure


def evaluate_impending_cross(
    history: pd.DataFrame,
    *,
    short_ma_slope: float,
    long_ma_slope: float,
    maximum_gap_percent: float,
    validation_sessions: int,
) -> tuple[CrossSetup | None, RuleFailure | None]:
    latest = history.iloc[-1]
    gap_percent = (
        (latest["MA_LONG"] - latest["MA_SHORT"]) / latest["MA_LONG"]
    ) * 100
    if gap_percent > maximum_gap_percent:
        return None, RuleFailure(
            "Impending Golden Cross Validation",
            "Short MA is farther below Long MA than the configured maximum gap",
        )
    if short_ma_slope <= long_ma_slope:
        return None, RuleFailure(
            "Impending Golden Cross Validation",
            "Short MA 5-session slope is not greater than Long MA 5-session slope",
        )
    validation = history[["MA_SHORT", "MA_LONG"]].dropna().iloc[
        -(validation_sessions + 1) : -1
    ]
    if len(validation) < validation_sessions or not (
        validation["MA_SHORT"] < validation["MA_LONG"]
    ).all():
        return None, RuleFailure(
            "Impending Golden Cross Validation",
            "Short MA was not strictly below Long MA throughout the configured pre-cross validation period",
        )
    return (
        CrossSetup(
            strategy="Impending Golden Cross",
            is_post_cross=False,
            cross={"valid": False, "cross_date": None, "days_since_cross": None},
            cross_date=None,
            gap_percent=float(gap_percent),
        ),
        None,
    )
