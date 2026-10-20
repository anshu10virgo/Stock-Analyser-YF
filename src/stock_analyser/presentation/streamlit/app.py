"""Packaged Streamlit composition root for the guided workflow."""

import streamlit as st

from stock_analyser import PROJECT_ROOT
from stock_analyser.presentation.streamlit.components.theme import apply_app_theme, render_app_header
from stock_analyser.presentation.streamlit.components.ticksy import render_ticksy
from stock_analyser.presentation.streamlit.navigation import NAVIGATION_OPTIONS, initialise_session
from stock_analyser.presentation.streamlit.pages.backtester import render_backtester_page
from stock_analyser.presentation.streamlit.pages.live_scan import render_live_scan_page
from stock_analyser.presentation.streamlit.pages.results import render_results_page
from stock_analyser.presentation.streamlit.pages.setup import render_setup_page
from stock_analyser.presentation.streamlit.pages.strategy import render_strategy_page
from stock_analyser.presentation.streamlit.session_adapter import current_session


def run() -> None:
    """Render the application shell and selected packaged page controller."""
    st.set_page_config(page_title="Stock Analyser", layout="wide")
    apply_app_theme()
    initialise_session()
    render_app_header()

    with st.container(key="workflow_navigation"):
        section = st.radio(
            "Workflow",
            NAVIGATION_OPTIONS,
            horizontal=True,
            label_visibility="collapsed",
            key="app_section",
        )

    pages = {
        "1. Setup": render_setup_page,
        "2. Strategy": render_strategy_page,
        "3. Live Scan": render_live_scan_page,
        "4. Results": render_results_page,
        "5. Backtester": lambda: render_backtester_page(PROJECT_ROOT),
    }
    pages[current_session().get("app_section", section)]()
    render_ticksy()


__all__ = ["run"]
