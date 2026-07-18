import streamlit as st
from datetime import datetime
from pathlib import Path

from core.data_loader import DataLoader
from models.scan_config import ScanConfig
from services.scan_service import ScanService

from ui.sidebar import render_scan_configuration
from ui.results_page import render_optional_failures, render_results


DEFAULT_SYMBOLS_FILE = Path(__file__).with_name("stock_symbols.csv")


st.set_page_config(
    page_title="Stock Analyser YF",
    layout="wide"
)

st.title(
    "Stock Analyser YF"
)

if st.session_state.pop("open_results_after_scan", False):
    st.session_state["app_section"] = "3. Results"

section = st.radio(
    "Navigate",
    options=("1. Data", "2. Scan", "3. Results"),
    horizontal=True,
    label_visibility="collapsed",
    key="app_section",
)

if section == "1. Data":
    source = st.radio(
        "Stock universe",
        options=("Included stock_symbols.csv", "Upload another file"),
        horizontal=True,
        key="stock_source",
    )
    uploaded_file = None
    if source == "Upload another file":
        uploaded_file = st.file_uploader("Upload CSV / Excel", type=["csv", "xlsx"])

    try:
        if source == "Upload another file" and uploaded_file is None:
            symbols = []
        elif uploaded_file is not None:
            symbols = DataLoader.load_symbols(uploaded_file, uploaded_file.name)
        else:
            symbols = DataLoader.load_symbols(DEFAULT_SYMBOLS_FILE)
    except ValueError as error:
        st.error(f"Could not read the stock universe: {error}")
        symbols = []

    if source == "Upload another file" and uploaded_file is None:
        st.session_state.pop("selected_symbols", None)
        st.info("Upload a CSV or Excel file to use a different stock universe.")
    elif symbols:
        st.session_state["selected_symbols"] = symbols
        st.success(f"{len(symbols):,} symbols available for scanning.")

elif section == "2. Scan":
    symbols = st.session_state.get("selected_symbols", [])
    if not symbols:
        st.info("Choose a valid stock universe in the Data tab first.")
    else:
        stock_count = st.number_input(
            "How many stocks do you want to analyse?",
            min_value=1,
            max_value=len(symbols),
            value=min(50, len(symbols)),
            step=1,
            help="The scanner uses the first N symbols in the selected file.",
        )
        settings = render_scan_configuration()
        symbols_to_scan = symbols[:stock_count]

        if st.button("Run Scan", type="primary"):
            config = ScanConfig(
                short_ma=settings["short_ma"],
                long_ma=settings["long_ma"],
                max_cross_age=settings["cross_age"],
                pre_cross_days=settings["pre_cross_days"],
                slope_lookback=settings["slope_lookback"],
                max_distance=settings["max_distance"],
                require_pre_cross_trough=settings["require_pre_cross_trough"],
                require_pre_cross_decline=settings["require_pre_cross_decline"],
                require_post_cross_sessions=settings[
                    "require_post_cross_sessions"
                ],
                require_post_cross_increase=settings[
                    "require_post_cross_increase"
                ],
                adjusted_prices=settings["adjusted_prices"],
            )
            progress_bar = st.progress(0)
            status = st.empty()

            with st.spinner("Scanning stocks..."):
                scan_result = ScanService(config).scan(
                    symbols_to_scan,
                    progress_callback=lambda current, total: (
                        progress_bar.progress(current / total),
                        status.text(f"Processing {current}/{total} symbols"),
                    ),
                ).as_dataframes()

            st.session_state["scan_results"] = scan_result["passed"]
            st.session_state["scan_failed_results"] = scan_result["failed"]
            st.session_state["scan_time"] = datetime.now()
            st.session_state["scan_settings"] = settings
            st.session_state["open_results_after_scan"] = True
            st.rerun()

elif section == "3. Results":
    if "scan_results" not in st.session_state:
        st.info("Run a scan from the Scan tab to see results.")
    else:
        render_results(
            st.session_state["scan_results"],
            st.session_state["scan_time"],
            st.session_state["scan_settings"],
        )
        optional_selected = any(
            st.session_state["scan_settings"][key]
            for key in (
                "require_pre_cross_trough",
                "require_pre_cross_decline",
                "require_post_cross_sessions",
                "require_post_cross_increase",
            )
        )
        if optional_selected and st.checkbox("Show stocks rejected by optional checks"):
            render_optional_failures(st.session_state["scan_failed_results"])
