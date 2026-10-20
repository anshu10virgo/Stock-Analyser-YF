"""Strategy configuration and scan-launch page."""

import streamlit as st

from stock_analyser.infrastructure.data_services import (
    LIVE_SOURCE,
    SNAPSHOT_SOURCE,
    snapshot_source_label,
)
from stock_analyser.infrastructure.r2 import config as storage_config
from stock_analyser import PROJECT_ROOT
from stock_analyser.presentation.streamlit.components.strategy_configuration import render_scan_configuration
from stock_analyser.presentation.streamlit.configuration import build_scan_config
from stock_analyser.presentation.streamlit.navigation import MARKET_DATA_SESSION_KEY, navigate_to
from stock_analyser.presentation.streamlit.session_adapter import current_session


def render_strategy_page() -> None:
    session = current_session()
    symbols = session.get("selected_symbols", [])
    if not symbols:
        st.info("Complete Setup before configuring a strategy.")
        if st.button("Go to Setup"):
            navigate_to("1. Setup")
        return

    st.subheader("Choose a scanning strategy")
    st.markdown(
        '<div class="sa-section-note">System defaults remain fixed. Any named '
        "strategies are stored only in this Streamlit session.</div>",
        unsafe_allow_html=True,
    )
    settings = render_scan_configuration()
    count = min(int(session.get("stock_count", 2000)), len(symbols))
    source = session.get(MARKET_DATA_SESSION_KEY, LIVE_SOURCE)
    st.divider()
    review = st.columns(3)
    review[0].metric("Stocks", f"{count:,}")
    source_label = "Live Yahoo"
    if source == SNAPSHOT_SOURCE:
        source_label = snapshot_source_label(
            storage_config.application_snapshot_storage(PROJECT_ROOT).cloud
        )
    review[1].metric("Data source", source_label)
    review[2].metric(
        "Result groups",
        "Post + Impending" if settings["include_impending_crosses"] else "Post Cross",
    )

    actions = st.columns(2)
    if actions[0].button("Run scan", type="primary"):
        try:
            build_scan_config(settings).validate()
        except ValueError as error:
            st.error(str(error))
        else:
            session["pending_scan"] = {
                "symbols": symbols[:count],
                "settings": settings,
                "market_data_source": source,
            }
            navigate_to("3. Live Scan")
    if actions[1].button("Backtest a stock", type="primary"):
        try:
            build_scan_config(settings).validate()
        except ValueError as error:
            st.error(str(error))
        else:
            session["backtest_settings"] = settings
            navigate_to("5. Backtester")


__all__ = ["render_strategy_page"]
