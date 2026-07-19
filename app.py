import streamlit as st
from datetime import datetime
from pathlib import Path

from core.data_loader import DataLoader
from models.scan_config import ScanConfig
from services.scan_service import ScanService
from services.stock_universe import StockUniverse

from ui.sidebar import render_scan_configuration
from ui.introduction_page import render_introduction
from ui.results_page import render_optional_failures, render_results


DEFAULT_SYMBOLS_FILE = Path(__file__).with_name("stock_symbols.csv")
STOCK_UNIVERSE = StockUniverse(
    Path(__file__).parent / "data" / "stock_universe",
    DEFAULT_SYMBOLS_FILE,
)


st.set_page_config(
    page_title="Stock Analyser YF",
    layout="wide"
)

st.title(
    "Stock Analyser YF"
)

if st.session_state.pop("open_results_after_scan", False):
    st.session_state["app_section"] = "3. Results"

if st.session_state.get("app_section") == "1. Data":
    st.session_state["app_section"] = "1. Introduction"

if st.session_state.get("stock_source") == "Included stock_symbols.csv":
    st.session_state["stock_source"] = "Included validated stock universe"

section = st.radio(
    "Navigate",
    options=("1. Introduction", "2. Scan", "3. Results"),
    horizontal=True,
    label_visibility="collapsed",
    key="app_section",
)

if section == "1. Introduction":
    render_introduction()
    st.divider()
    st.subheader("Choose stock universe")
    source = st.radio(
        "Stock universe",
        options=("Included validated stock universe", "Upload another file"),
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
            symbols = DataLoader.load_symbols(STOCK_UNIVERSE.active_file())
    except ValueError as error:
        st.error(f"Could not read the stock universe: {error}")
        symbols = []

    if source == "Upload another file" and uploaded_file is None:
        st.session_state.pop("selected_symbols", None)
        st.info("Upload a CSV or Excel file to use a different stock universe.")
    elif symbols:
        st.session_state["selected_symbols"] = symbols
        st.success(f"{len(symbols):,} symbols available for scanning.")
        metadata = STOCK_UNIVERSE.metadata()
        if metadata.get("refreshed_at"):
            st.caption(f"Active stock universe refreshed: {metadata['refreshed_at']}")

elif section == "2. Scan":
    symbols = st.session_state.get("selected_symbols", [])
    if not symbols:
        st.info("Choose a valid stock universe in the Data tab first.")
    else:
        stock_count = st.number_input(
            "How many of the highest market-cap stocks do you want to analyse?",
            min_value=1,
            max_value=len(symbols),
            value=min(1500, len(symbols)),
            step=1,
            help="For the included universe, the scanner uses the top N stored market-cap ranks. Uploaded files use their Market Cap Rank column when provided.",
        )
        settings = render_scan_configuration()
        symbols_to_scan = symbols[:stock_count]

        if st.button("Run Scan", type="primary"):
            config = ScanConfig(
                short_ma=settings["short_ma"],
                long_ma=settings["long_ma"],
                max_cross_age=settings["cross_age"],
                min_long_ma_decline_duration=settings["min_long_ma_decline_duration"],
                min_long_ma_decline=settings["min_long_ma_decline"],
                max_price_premium=settings["max_price_premium"],
                require_post_cross_sessions=settings[
                    "require_post_cross_sessions"
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
                "require_post_cross_sessions",
            )
        )
        if optional_selected and st.checkbox("Show stocks rejected by optional checks"):
            render_optional_failures(st.session_state["scan_failed_results"])
