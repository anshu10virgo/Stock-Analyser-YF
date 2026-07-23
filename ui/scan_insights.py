"""Locally derived scan summaries for live and completed results."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st


REJECTION_LABELS = {
    "Unable to download market data for this scan": "Market data could not be downloaded",
    "No complete market data was returned for the symbol": "No complete price history is available",
    "Short MA 5-session slope is not positive": "Short MA is not rising",
    "No Golden Cross within the configured age": "No recent Golden Cross",
    "Short MA is not above Long MA": "Short MA has not crossed above Long MA",
    "Short MA is farther below Long MA than the configured maximum gap": "Moving averages are farther apart than allowed",
    "Short MA 5-session slope is not greater than Long MA 5-session slope": "Short MA is not converging faster than Long MA",
    "Short MA was not strictly below Long MA throughout the configured pre-cross validation period": "Pre-cross trend was not stable for the selected period",
    "Insufficient Long MA history for 52-week high": "Not enough Long-MA history",
    "Long MA decline from 52-week high to trough is below configured minimum": "Long-MA decline is smaller than required",
    "Long MA decline from 52-week high to trough is shorter than configured minimum duration": "Long-MA decline duration is shorter than required",
    "Post-trough 5-session Long MA slope is not positive": "Long MA has not started rising after its trough",
    "Long MA is below its trough or its latest 5-session slope is negative": "Long MA is still falling",
    "Close price is not above Long MA": "Current price is not above Long MA",
    "Close price is too far above Long MA": "Current price is too far above Long MA",
    "Golden Cross needs 10 post-cross sessions": "Golden Cross has fewer than 10 completed sessions",
    "Unexpected error while evaluating the symbol": "Stock could not be evaluated",
}


def friendly_rejection(reason: str) -> str:
    """Translate internal scanner wording into a compact user-facing label."""
    return REJECTION_LABELS.get(reason, reason)


def derive_scan_insights(passed: pd.DataFrame, failed: pd.DataFrame | None = None) -> dict:
    """Derive useful labels only from fields already produced by the scanner."""
    insights: dict[str, str] = {}
    if not passed.empty:
        if "score" in passed:
            best = passed.loc[passed["score"].idxmax()]
            insights["Highest score"] = f"{best['symbol']} · {best['score']:.0f}"
        if "days_since_cross" in passed and passed["days_since_cross"].notna().any():
            newest = passed.loc[passed["days_since_cross"].idxmin()]
            insights["Newest Golden Cross"] = (
                f"{newest['symbol']} · {newest['days_since_cross']:.0f} days"
            )
        required = {"pe", "industry_median_pe", "symbol"}
        if required.issubset(passed.columns):
            valuation = passed.dropna(subset=["pe", "industry_median_pe"]).copy()
            if not valuation.empty:
                valuation["industry_pe_discount"] = (
                    valuation["industry_median_pe"] - valuation["pe"]
                )
                discounted = valuation.loc[valuation["industry_pe_discount"].idxmax()]
                insights["Largest industry PE discount"] = (
                    f"{discounted['symbol']} · {discounted['industry_pe_discount']:.2f}"
                )
        if "long_ma_recovery_slope" in passed and passed["long_ma_recovery_slope"].notna().any():
            recovery = passed.loc[passed["long_ma_recovery_slope"].idxmax()]
            insights["Strongest Long-MA recovery"] = recovery["symbol"]

    if failed is not None and not failed.empty:
        if "reason" in failed and failed["reason"].notna().any():
            rejections = Counter(
                friendly_rejection(reason)
                for reason in failed["reason"].dropna().astype(str)
            )
        elif "stage" in failed:
            rejections = Counter(failed["stage"].dropna().astype(str))
        else:
            rejections = Counter()
        if rejections:
            reason, count = rejections.most_common(1)[0]
            insights["Most common rejection"] = f"{reason} · {count:,} stocks"
    return insights


def render_scan_insights(
    passed: pd.DataFrame,
    failed: pd.DataFrame | None = None,
    *,
    heading: str = "Local scan insights",
) -> None:
    """Render a compact summary without external requests or new calculations."""
    st.subheader(heading)
    insights = derive_scan_insights(passed, failed)
    if not insights:
        st.caption("Insights will appear when qualified or rejected stocks are available.")
        return
    columns = st.columns(min(3, len(insights)))
    for index, (label, value) in enumerate(insights.items()):
        columns[index % len(columns)].metric(label, value)
    st.caption("Derived only from the current scan; no external research request is made.")
