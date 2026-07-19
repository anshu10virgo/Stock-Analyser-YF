"""Streamlit entry point for the guided Stock Analyser workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from core.data_loader import DataLoader
from models.scan_config import ScanConfig
from services.data_source import LIVE_SOURCE, SNAPSHOT_SOURCE, build_data_services
from services.scan_service import ScanService
from services.stock_universe import StockUniverse
from ui.introduction_page import render_introduction
from ui.results_page import prepare_results, render_optional_failures, render_results
from ui.scan_insights import render_scan_insights
from ui.sidebar import render_scan_configuration
from ui.theme import apply_app_theme, render_app_header, scroll_to_top


PROJECT_ROOT = Path(__file__).parent
DEFAULT_SYMBOLS_FILE = PROJECT_ROOT / "stock_symbols.csv"
HERO_IMAGE = PROJECT_ROOT / "assets" / "stock-market-bull-bear.webp"
MARKET_DATA_SESSION_KEY = "selected_market_data_source"
MARKET_DATA_WIDGET_KEY = "market_data_source_selector"
NAVIGATION_OPTIONS = (
    "1. Setup",
    "2. Strategy",
    "3. Live Scan",
    "4. Results",
)
STOCK_UNIVERSE = StockUniverse(
    PROJECT_ROOT / "data" / "stock_universe",
    DEFAULT_SYMBOLS_FILE,
)


def _initialise_session() -> None:
    """Initialise durable workflow choices independently of widget lifecycle."""
    if MARKET_DATA_SESSION_KEY not in st.session_state:
        st.session_state[MARKET_DATA_SESSION_KEY] = LIVE_SOURCE
    if st.session_state.get("app_section") not in NAVIGATION_OPTIONS:
        st.session_state["app_section"] = "1. Setup"
    requested_section = st.session_state.pop("_next_app_section", None)
    if requested_section in NAVIGATION_OPTIONS:
        st.session_state["app_section"] = requested_section
    if st.session_state.get("stock_source") == "Included stock_symbols.csv":
        st.session_state["stock_source"] = "Included validated stock universe"


def _navigate_to(section: str) -> None:
    """Request navigation before the workflow radio is recreated on rerun."""
    st.session_state["_next_app_section"] = section
    st.rerun()


def _render_hero() -> None:
    copy, artwork = st.columns((0.9, 1.35), vertical_alignment="center")
    copy.markdown(
        """
        <div class="sa-hero-copy">
          <div class="sa-kicker">MARKET INTELLIGENCE</div>
          <h2>Find technically strong stocks without the noise.</h2>
          <div class="sa-accent-rule"></div>
          <p>Configure the market once, apply a strategy, and follow qualified
          stocks as the scan progresses.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if HERO_IMAGE.is_file():
        artwork.image(str(HERO_IMAGE), width="stretch")


def _load_symbols(source: str, uploaded_file) -> list[str]:
    if source == "Upload another file" and uploaded_file is None:
        return []
    if uploaded_file is not None:
        return DataLoader.load_symbols(uploaded_file, uploaded_file.name)
    return DataLoader.load_symbols(STOCK_UNIVERSE.active_file())


def _render_snapshot_status(source: str) -> None:
    if source != SNAPSHOT_SOURCE:
        st.info("Scans will retrieve market history from live Yahoo Finance.")
        return
    metadata = build_data_services(SNAPSHOT_SOURCE, PROJECT_ROOT).metadata
    if not metadata.get("last_trading_date"):
        st.warning("No committed snapshot is available. Missing requests will use Yahoo.")
        return
    st.success(f"Git snapshot available through {metadata['last_trading_date']}.")
    coverage = metadata.get("fundamentals_coverage", {})
    if coverage:
        st.caption(
            "Fundamentals coverage: "
            f"PE {coverage.get('pe', 0):,}/{metadata.get('symbol_count', 0):,}; "
            f"industry {coverage.get('industry', 0):,}/{metadata.get('symbol_count', 0):,}; "
            f"industry benchmarks {coverage.get('industries_with_valuations', 0):,}."
        )


def render_setup_page() -> None:
    """Render market, universe, and source choices as the first workflow step."""
    _render_hero()
    st.subheader("Market and data setup")
    st.caption("Complete these choices once; they remain active for this session.")
    market_col, universe_col = st.columns(2)
    market_col.selectbox(
        "Stock market",
        ("India — NSE",),
        help="United States support is planned but is not active yet.",
    )
    source = universe_col.radio(
        "Stock universe",
        ("Included validated stock universe", "Upload another file"),
        horizontal=True,
        key="stock_source",
    )
    uploaded_file = None
    if source == "Upload another file":
        uploaded_file = st.file_uploader("Upload CSV or Excel", type=("csv", "xlsx"))

    selected_source = st.radio(
        "Market-data source",
        (LIVE_SOURCE, SNAPSHOT_SOURCE),
        horizontal=True,
        index=(LIVE_SOURCE, SNAPSHOT_SOURCE).index(
            st.session_state[MARKET_DATA_SESSION_KEY]
        ),
        key=MARKET_DATA_WIDGET_KEY,
        help="Git snapshot uses committed data and contacts Yahoo only for missing snapshot data.",
    )
    st.session_state[MARKET_DATA_SESSION_KEY] = selected_source
    _render_snapshot_status(selected_source)

    try:
        symbols = _load_symbols(source, uploaded_file)
    except ValueError as error:
        st.error(f"Could not read the stock universe: {error}")
        symbols = []

    if symbols:
        st.session_state["selected_symbols"] = symbols
        maximum = len(symbols)
        current = min(int(st.session_state.get("stock_count", 1500)), maximum)
        st.number_input(
            "Highest market-cap stocks to analyse",
            min_value=1,
            max_value=maximum,
            value=current,
            step=1,
            key="stock_count",
            help="The included universe is ordered by stored market-cap rank.",
        )
        metadata = STOCK_UNIVERSE.metadata()
        st.success(f"{len(symbols):,} ranked symbols are available.")
        if metadata.get("refreshed_at"):
            st.caption(f"Active universe refreshed: {metadata['refreshed_at']}")
    elif source == "Upload another file":
        st.session_state.pop("selected_symbols", None)
        st.info("Upload a CSV or Excel file to continue with a different universe.")

    with st.expander("How screening and scoring work"):
        render_introduction()

    if st.button("Continue to strategy", type="primary", disabled=not bool(symbols)):
        _navigate_to("2. Strategy")


def _build_config(settings: dict) -> ScanConfig:
    return ScanConfig(
        short_ma=settings["short_ma"],
        long_ma=settings["long_ma"],
        max_cross_age=settings["cross_age"],
        min_long_ma_decline_duration=settings["min_long_ma_decline_duration"],
        min_long_ma_decline=settings["min_long_ma_decline"],
        max_price_premium=settings["max_price_premium"],
        require_post_cross_sessions=settings["require_post_cross_sessions"],
        adjusted_prices=settings["adjusted_prices"],
    )


def render_strategy_page() -> None:
    """Render session strategies and queue a scan for the dedicated live view."""
    symbols = st.session_state.get("selected_symbols", [])
    if not symbols:
        st.info("Complete Setup before configuring a strategy.")
        if st.button("Go to Setup"):
            _navigate_to("1. Setup")
        return

    st.subheader("Choose a scanning strategy")
    st.markdown(
        '<div class="sa-section-note">System defaults remain fixed. Any named '
        "strategies are stored only in this Streamlit session.</div>",
        unsafe_allow_html=True,
    )
    settings = render_scan_configuration()
    count = min(int(st.session_state.get("stock_count", 1500)), len(symbols))
    source = st.session_state.get(MARKET_DATA_SESSION_KEY, LIVE_SOURCE)
    st.divider()
    review = st.columns(3)
    review[0].metric("Stocks", f"{count:,}")
    review[1].metric("Data source", "Git snapshot" if source == SNAPSHOT_SOURCE else "Live Yahoo")
    review[2].metric("Optional checks", "1" if settings["require_post_cross_sessions"] else "None")

    if st.button("Run scan", type="primary"):
        st.session_state["pending_scan"] = {
            "symbols": symbols[:count],
            "settings": settings,
            "market_data_source": source,
        }
        _navigate_to("3. Live Scan")


def _live_update(index: int, total: int, run, placeholders: dict) -> None:
    """Refresh local results in batches to avoid slowing the scan."""
    placeholders["progress"].progress(index / total)
    placeholders["processed"].metric("Processed", f"{index:,} / {total:,}")
    placeholders["qualified"].metric("Qualified", f"{len(run.passed):,}")
    placeholders["rejected"].metric("Rejected", f"{len(run.failed):,}")
    if index % 25 and index != total:
        return
    frames = run.as_dataframes()
    with placeholders["results"].container():
        st.subheader("Qualified stocks so far")
        if frames["passed"].empty:
            st.caption("No stocks have qualified in the processed batch yet.")
        else:
            st.dataframe(
                prepare_results(frames["passed"]).head(10),
                width="stretch",
                hide_index=True,
            )
    with placeholders["insights"].container():
        render_scan_insights(frames["passed"], frames["failed"])


def render_live_scan_page() -> None:
    """Execute a queued scan and publish progressive local information."""
    scroll_to_top()
    pending = st.session_state.get("pending_scan")
    if not pending:
        st.subheader("Live scan")
        st.info("No scan is currently running. Configure and start one from Strategy.")
        if st.button("Go to Strategy"):
            _navigate_to("2. Strategy")
        return

    symbols = pending["symbols"]
    settings = pending["settings"]
    source = pending["market_data_source"]
    st.subheader(f"Scanning {len(symbols):,} stocks")
    st.caption("Qualified stocks and locally derived insights update every 25 symbols.")
    progress = st.progress(0)
    metric_columns = st.columns(3)
    placeholders = {
        "progress": progress,
        "processed": metric_columns[0].empty(),
        "qualified": metric_columns[1].empty(),
        "rejected": metric_columns[2].empty(),
        "results": st.empty(),
        "insights": st.empty(),
    }
    data_services = build_data_services(source, PROJECT_ROOT)
    settings = {
        **settings,
        "market_data_source": source,
        "market_data_snapshot": data_services.metadata,
    }
    scan_run = ScanService(
        _build_config(settings),
        data_provider=data_services.history,
        fundamentals_provider=data_services.fundamentals,
        industry_valuation_service=data_services.industry_valuation,
    ).scan(
        symbols,
        result_callback=lambda current, total, run: _live_update(
            current, total, run, placeholders
        ),
    )
    frames = scan_run.as_dataframes()
    st.session_state["scan_results"] = frames["passed"]
    st.session_state["scan_failed_results"] = frames["failed"]
    st.session_state["scan_time"] = datetime.now()
    st.session_state["scan_settings"] = settings
    st.session_state["scan_metrics"] = scan_run.metrics
    st.session_state.pop("pending_scan", None)
    _navigate_to("4. Results")


def render_results_page() -> None:
    """Render the completed scan and optional-check failures."""
    if "scan_results" not in st.session_state:
        st.info("Run a scan from Strategy to see results.")
        return
    results = st.session_state["scan_results"]
    failed = st.session_state.get("scan_failed_results", pd.DataFrame())
    render_scan_insights(results, failed, heading="Scan highlights")
    render_results(
        results,
        st.session_state["scan_time"],
        st.session_state["scan_settings"],
        st.session_state.get("scan_metrics", {}),
    )
    if (
        st.session_state["scan_settings"].get("require_post_cross_sessions")
        and st.checkbox("Show stocks rejected by optional checks")
    ):
        render_optional_failures(failed)


st.set_page_config(page_title="Stock Analyser", layout="wide")
apply_app_theme()
_initialise_session()
render_app_header()

with st.container(key="workflow_navigation"):
    section = st.radio(
        "Workflow",
        NAVIGATION_OPTIONS,
        horizontal=True,
        label_visibility="collapsed",
        key="app_section",
    )

if section == "1. Setup":
    render_setup_page()
elif section == "2. Strategy":
    render_strategy_page()
elif section == "3. Live Scan":
    render_live_scan_page()
else:
    render_results_page()
