"""Pure date, valuation, return, and aggregation calculations for backtests."""

from __future__ import annotations

import pandas as pd

from stock_analyser.domain.backtesting.horizons import HORIZON_SESSIONS
from stock_analyser.domain.backtesting.models import ReturnSummary


def within_cross_age(cross_date, evaluation_date, maximum_age_days: int) -> bool:
    return (evaluation_date - cross_date).days <= maximum_age_days


def forward_returns(
    history: pd.DataFrame,
    entry_position: int,
    entry_price: float,
    horizons: dict[str, int] | None = None,
) -> dict[str, float | None]:
    returns: dict[str, float | None] = {}
    for label, sessions in (horizons or HORIZON_SESSIONS).items():
        exit_position = entry_position + sessions
        returns[label] = (
            None
            if exit_position >= len(history)
            else round(
                ((history.iloc[exit_position]["Close"] / entry_price) - 1) * 100,
                2,
            )
        )
    return returns


def valuation_at(
    valuation_history: pd.DataFrame | None,
    signal_date,
) -> tuple[float | None, object | None]:
    if valuation_history is None or valuation_history.empty:
        return None, None
    eligible = valuation_history.loc[
        valuation_history["date"].le(signal_date) & valuation_history["pe"].gt(0)
    ]
    if eligible.empty:
        return None, None
    latest = eligible.iloc[-1]
    return float(latest["pe"]), latest["date"].to_pydatetime()


def summarize_returns(values: pd.Series, *, signal_count: int) -> ReturnSummary:
    observed = pd.to_numeric(values, errors="coerce").dropna()
    return ReturnSummary(
        signal_count=signal_count,
        observed_count=len(observed),
        average_return=None if observed.empty else float(observed.mean()),
        median_return=None if observed.empty else float(observed.median()),
    )


__all__ = ["forward_returns", "summarize_returns", "valuation_at", "within_cross_age"]
