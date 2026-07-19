"""Locally derived scan summaries for live and completed results."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st


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

    if failed is not None and not failed.empty and "stage" in failed:
        stages = Counter(failed["stage"].dropna())
        if stages:
            stage, count = stages.most_common(1)[0]
            insights["Most common rejection"] = f"{stage} · {count:,} stocks"
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
