"""Introduction and scoring guide for first-time users."""

import pandas as pd
import streamlit as st


def render_introduction() -> None:
    """Explain the scanner workflow and its transparent 85-point ranking."""
    st.subheader("About Stock Analyser")
    st.write(
        "Stock Analyser is a technical stock-screening tool for NSE stocks "
        "using Yahoo Finance market data. It identifies completed Post Golden "
        "Cross opportunities and, when selected, stocks approaching an "
        "Impending Golden Cross. Shared price and trend checks are applied "
        "before each strategy's unique mandatory rules."
    )

    st.subheader("How the scan works")
    st.markdown(
        "1. Complete the market and data setup once for the session.\n"
        "2. Load a session strategy or configure the checks.\n"
        "3. Follow scan progress and locally derived insights as stocks are processed.\n"
        "4. Review separate Post and Impending results, one-year trends, and Post-Cross score details."
    )

    st.subheader("How the score is calculated")
    st.caption("Total possible score: 85 points. The score ranks qualified Post Golden Cross stocks only; Impending results are ordered by MA proximity and trajectory.")
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
        width="stretch",
        hide_index=True,
    )

    st.info(
        "Results are analytical screening information, not investment advice. "
        "Yahoo Finance data may be delayed, incomplete, or unavailable for some symbols."
    )
