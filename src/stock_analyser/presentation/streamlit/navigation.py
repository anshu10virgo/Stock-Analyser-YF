"""Workflow navigation backed by the session adapter."""

import streamlit as st

from services.data_source import LIVE_SOURCE, SNAPSHOT_SOURCE
from stock_analyser.presentation.streamlit.session_adapter import current_session


NAVIGATION_OPTIONS = (
    "1. Setup",
    "2. Strategy",
    "3. Live Scan",
    "4. Results",
    "5. Backtester",
)
MARKET_DATA_SESSION_KEY = "selected_market_data_source"
MARKET_DATA_WIDGET_KEY = "market_data_source_selector"


def initialise_session() -> None:
    session = current_session()
    if MARKET_DATA_SESSION_KEY not in session:
        try:
            storage_provider = st.secrets.get("storage", {}).get("provider", "local")
        except FileNotFoundError:
            storage_provider = "local"
        session[MARKET_DATA_SESSION_KEY] = (
            SNAPSHOT_SOURCE if storage_provider in {"r2", "s3"} else LIVE_SOURCE
        )
    if session.get("app_section") not in NAVIGATION_OPTIONS:
        session["app_section"] = "1. Setup"
    requested_section = session.pop("_next_app_section", None)
    if requested_section in NAVIGATION_OPTIONS:
        session["app_section"] = requested_section


def navigate_to(section: str) -> None:
    if section not in NAVIGATION_OPTIONS:
        raise ValueError(f"Unknown workflow section: {section}")
    current_session().request_navigation(section)


__all__ = [
    "MARKET_DATA_SESSION_KEY",
    "MARKET_DATA_WIDGET_KEY",
    "NAVIGATION_OPTIONS",
    "initialise_session",
    "navigate_to",
]
