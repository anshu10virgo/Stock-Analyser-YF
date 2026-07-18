import streamlit as st
from pathlib import Path

from core.data_loader import DataLoader
from core.scanner import StockScanner

from ui.sidebar import render_sidebar
from ui.results_page import render_results


DEFAULT_SYMBOLS_FILE = Path(__file__).with_name("stock_symbols.csv")


st.set_page_config(
    page_title="Stock Analyser YF",
    layout="wide"
)

st.title(
    "Stock Analyser YF"
)

settings = render_sidebar()

source = st.radio(
    "Stock universe",
    options=("Included stock_symbols.csv", "Upload another file"),
    horizontal=True,
)

uploaded_file = None
if source == "Upload another file":
    uploaded_file = st.file_uploader(
        "Upload CSV / Excel",
        type=["csv", "xlsx"],
    )

    if uploaded_file is None:
        st.info("Upload a CSV or Excel file to use a different stock universe.")
        st.stop()

try:
    if uploaded_file is not None:
        symbols = DataLoader.load_symbols(
            uploaded_file,
            uploaded_file.name,
        )
    else:
        symbols = DataLoader.load_symbols(DEFAULT_SYMBOLS_FILE)
except ValueError as error:
    st.error(f"Could not read the stock universe: {error}")
    st.stop()

st.caption(f"{len(symbols):,} symbols available")
stock_count = st.number_input(
    "How many stocks do you want to analyse?",
    min_value=1,
    max_value=len(symbols),
    value=min(50, len(symbols)),
    step=1,
    help="The scanner uses the first N symbols in the selected file.",
)
symbols_to_scan = symbols[:stock_count]

if st.button("Run Scan"):
    scanner = StockScanner(
        short_ma=settings["short_ma"],
        long_ma=settings["long_ma"],
        max_cross_age=settings["cross_age"],
        pre_cross_days=settings["pre_cross_days"],
        trough_lookback=settings["trough_lookback"],
        min_troughs=settings["min_troughs"],
        slope_lookback=settings["slope_lookback"],
        max_distance=settings["max_distance"],
        adjusted_prices=settings["adjusted_prices"],
    )

    progress_bar = st.progress(0)
    status = st.empty()

    with st.spinner("Scanning stocks..."):
        scan_result = scanner.scan(
            symbols_to_scan,
            progress_callback=lambda current, total: (
                progress_bar.progress(current / total),
                status.text(f"Processing {current}/{total} symbols"),
            ),
        )

    render_results(scan_result["passed"])
