"""Queries that summarise completed local scan and Backtest state."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


def get_scan_summary(state: Mapping) -> dict:
    def count(key: str) -> int:
        frame = state.get(key)
        return int(len(frame)) if isinstance(frame, pd.DataFrame) else 0

    return {
        "scan_time": str(state.get("scan_time")) if state.get("scan_time") else None,
        "post_golden_cross_count": count("scan_results"),
        "impending_golden_cross_count": count("scan_impending_results"),
        "failed_count": count("scan_failed_results"),
    }


def get_market_condition(state: Mapping) -> dict:
    summary = get_scan_summary(state)
    passed = state.get("scan_results")
    impending = state.get("scan_impending_results")
    failed = state.get("scan_failed_results")
    above_long = 0
    for frame in (passed, impending):
        if isinstance(frame, pd.DataFrame) and "price_above_long_ma_percent" in frame:
            above_long += int(
                (
                    pd.to_numeric(
                        frame["price_above_long_ma_percent"], errors="coerce"
                    )
                    > 0
                ).sum()
            )
    recent_crosses = 0
    if isinstance(passed, pd.DataFrame) and "days_since_cross" in passed:
        recent_crosses = int(
            (pd.to_numeric(passed["days_since_cross"], errors="coerce") <= 20).sum()
        )
    summary.update(
        {
            "above_long_ma_count": above_long,
            "recent_cross_count": recent_crosses,
            "failed_with_reason_count": (
                int(len(failed)) if isinstance(failed, pd.DataFrame) else 0
            ),
        }
    )
    return summary


def get_backtest_results(
    state: Mapping, symbols: list[str] | None = None
) -> list[dict]:
    frame = state.get("backtest_results")
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    selected = frame
    if symbols and "Stock" in frame.columns:
        selected = frame.loc[frame["Stock"].isin(symbols)]
    return selected.where(pd.notna(selected), None).to_dict("records")
