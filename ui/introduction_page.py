"""Introduction and scoring guide for first-time users."""

import pandas as pd
import streamlit as st


def render_introduction() -> None:
    """Explain the scanner workflow and its transparent 85-point ranking."""
    st.subheader("About Stock Analyser YF")
    st.write(
        "Stock Analyser YF is a technical stock-screening tool for NSE stocks "
        "using Yahoo Finance market data. It identifies recent Golden Cross "
        "opportunities, applies mandatory price and trend checks, and lets you "
        "apply additional optional filters."
    )

    st.subheader("How the scan works")
    st.markdown(
        "1. Choose the included stock universe or upload a CSV/Excel file.\n"
        "2. Select how many stocks to analyse and configure the checks.\n"
        "3. Stocks passing all mandatory and selected optional checks appear "
        "in Qualified Stocks.\n"
        "4. Qualified stocks are ranked using the score below."
    )

    st.subheader("How the score is calculated")
    st.caption("Total possible score: 85 points. Score ranks qualified stocks; it does not override any failed check.")
    st.dataframe(
        pd.DataFrame(
            [
                ("Golden Cross recency", "20 / 15 / 10", "More recent crosses receive more points."),
                ("Long-term trend", "20 / 15 / 5 / 0", "Strong positive, positive, flat, or negative slope."),
                ("Price position", "15 / 10 / 5 / 0", "Price proximity to the long-term moving average."),
                ("PE", "10 / 5 / 0", "Lower available PE receives more points."),
                ("EPS", "10 / 0", "Positive available EPS receives points."),
                ("Market capitalisation", "10 / 5 / 0", "Larger available market capitalisation receives points."),
            ],
            columns=["Factor", "Points", "How points are assigned"],
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.info(
        "Results are analytical screening information, not investment advice. "
        "Yahoo Finance data may be delayed, incomplete, or unavailable for some symbols."
    )
