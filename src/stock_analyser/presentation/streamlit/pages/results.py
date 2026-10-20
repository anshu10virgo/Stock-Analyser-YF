"""Completed scan results page controller."""

import pandas as pd
import streamlit as st

from stock_analyser.presentation.streamlit.components.results import (
    render_optional_failures,
    render_results,
    render_selected_stock,
)
from stock_analyser.presentation.streamlit.components.scan_insights import render_scan_insights
from stock_analyser.presentation.streamlit.session_adapter import current_session


def render_results_page() -> None:
    session = current_session()
    if "scan_results" not in session:
        st.info("Run a scan from Strategy to see results.")
        return
    results = session["scan_results"]
    impending = session.get("scan_impending_results", pd.DataFrame())
    failed = session.get("scan_failed_results", pd.DataFrame())
    render_scan_insights(results, failed, heading="Scan highlights")
    render_results(
        results,
        impending,
        session["scan_time"],
        session["scan_settings"],
        session.get("scan_metrics", {}),
    )
    requested_symbol = session.pop("ticksy_selected_symbol", None)
    if requested_symbol:
        combined = pd.concat([results, impending], ignore_index=True)
        if "symbol" in combined.columns:
            selected = combined.loc[combined["symbol"] == requested_symbol]
            if not selected.empty:
                st.divider()
                st.subheader(f"Ticksy selected: {requested_symbol}")
                render_selected_stock(
                    selected.iloc[0],
                    session["scan_settings"],
                    show_score=selected.iloc[0].get("strategy") != "Impending Golden Cross",
                )
            else:
                st.info(f"{requested_symbol} is not available in the current qualified Results.")
    if session["scan_settings"].get("optional_filters") and st.checkbox(
        "Show stocks rejected by optional checks"
    ):
        render_optional_failures(failed)


__all__ = ["render_results_page"]
