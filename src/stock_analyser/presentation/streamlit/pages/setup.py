"""Market, stock-universe, and data-source setup page."""

import streamlit as st

from stock_analyser.infrastructure.data_services import (
    LIVE_SOURCE,
    SNAPSHOT_SOURCE,
    build_data_services,
    snapshot_source_label,
)
from stock_analyser.infrastructure.local.data_loader import DataLoader
from stock_analyser.infrastructure.local.stock_universe import StockUniverse
from stock_analyser.infrastructure.r2 import config as storage_config
from stock_analyser.infrastructure.r2.storage import (
    ScopedSnapshotStorage,
    SnapshotStorageError,
)
from stock_analyser import PROJECT_ROOT
from stock_analyser.presentation.streamlit.navigation import (
    MARKET_DATA_SESSION_KEY,
    MARKET_DATA_WIDGET_KEY,
    navigate_to,
)
from stock_analyser.presentation.streamlit.pages.introduction import render_introduction
from stock_analyser.presentation.streamlit.session_adapter import current_session


HERO_IMAGE = PROJECT_ROOT / "assets" / "stock-market-bull-bear.webp"


def _stock_universe():
    return StockUniverse(
        PROJECT_ROOT / "data" / "stock_universe",
        storage=ScopedSnapshotStorage(
            storage_config.application_snapshot_storage(PROJECT_ROOT), "data/stock_universe"
        ),
    )


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
    return DataLoader.load_symbols(_stock_universe().active_file())


def _render_snapshot_status(source: str) -> None:
    if source != SNAPSHOT_SOURCE:
        st.info("Scans will retrieve market history from live Yahoo Finance.")
        return
    metadata = build_data_services(SNAPSHOT_SOURCE, PROJECT_ROOT).metadata
    if not metadata.get("last_trading_date"):
        st.warning("No stored snapshot is available. Configure cloud storage or download a local snapshot.")
        return
    label = snapshot_source_label(metadata.get("access_mode") == "cloud_snapshot")
    st.success(f"{label} available through {metadata['last_trading_date']}.")
    coverage = metadata.get("fundamentals_coverage", {})
    if coverage:
        st.caption(
            "Fundamentals coverage: "
            f"PE {coverage.get('pe', 0):,}/{metadata.get('symbol_count', 0):,}; "
            f"industry {coverage.get('industry', 0):,}/{metadata.get('symbol_count', 0):,}; "
            f"industry benchmarks {coverage.get('industries_with_valuations', 0):,}."
        )


def render_setup_page() -> None:
    session = current_session()
    _render_hero()
    st.subheader("Market and data setup")
    st.caption("Complete these choices once; they remain active for this session.")
    try:
        cloud_storage = storage_config.application_snapshot_storage(PROJECT_ROOT).cloud
    except SnapshotStorageError as error:
        st.error(str(error))
        return
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
        index=(LIVE_SOURCE, SNAPSHOT_SOURCE).index(session[MARKET_DATA_SESSION_KEY]),
        key=MARKET_DATA_WIDGET_KEY,
        format_func=lambda value: (
            snapshot_source_label(cloud_storage) if value == SNAPSHOT_SOURCE else value
        ),
        help="Stored snapshots use the configured storage. Cloud snapshots do not fall back to live data.",
    )
    session[MARKET_DATA_SESSION_KEY] = selected_source
    try:
        _render_snapshot_status(selected_source)
    except SnapshotStorageError as error:
        st.error(str(error))
        return

    try:
        symbols = _load_symbols(source, uploaded_file)
    except (ValueError, OSError, SnapshotStorageError) as error:
        st.error(f"Could not read the stock universe: {error}")
        symbols = []

    if symbols:
        session["selected_symbols"] = symbols
        maximum = len(symbols)
        current = min(int(session.get("stock_count", 2000)), maximum)
        st.number_input(
            "Highest market-cap stocks to analyse",
            min_value=1,
            max_value=maximum,
            value=current,
            step=1,
            key="stock_count",
            help="The included universe is ordered by stored market-cap rank.",
        )
        metadata = _stock_universe().metadata()
        st.success(f"{len(symbols):,} ranked symbols are available.")
        if metadata.get("refreshed_at"):
            st.caption(f"Active universe refreshed: {metadata['refreshed_at']}")
    elif source == "Upload another file":
        session.pop("selected_symbols", None)
        st.info("Upload a CSV or Excel file to continue with a different universe.")

    with st.expander("How screening and scoring work"):
        render_introduction()

    if st.button("Continue to strategy", type="primary", disabled=not bool(symbols)):
        navigate_to("2. Strategy")


__all__ = ["render_setup_page"]
