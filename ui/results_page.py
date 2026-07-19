import pandas as pd
import streamlit as st
from pathlib import Path

from core.indicators import Indicators
from ui.stock_detail import render_stock_detail
from services.data_source import LIVE_SOURCE, SNAPSHOT_SOURCE, build_data_services


DISPLAY_COLUMNS = {
    "symbol": "Symbol",
    "company_name": "Company Name",
    "sector": "Sector",
    "industry": "Industry",
    "score": "Score",
    "market_cap": "Market Cap",
    "close": "Close",
    "pe": "PE",
    "eps": "EPS",
    "ma_short": "Short MA",
    "ma_long": "Long MA",
    "cross_date": "Cross Date",
    "slope_label": "Slope Label",
}


SCORE_COMPONENTS = (
    ("score_cross", "Golden Cross Timing"),
    ("score_slope", "Long-term Trend"),
    ("score_distance", "Price Position"),
    ("score_pe", "PE"),
    ("score_eps", "EPS"),
    ("score_market_cap", "Market Capitalisation"),
)


def prepare_results(df):
    """Return scanner results with user-friendly labels and values."""
    results = df.reindex(columns=DISPLAY_COLUMNS).rename(columns=DISPLAY_COLUMNS)

    results["Company Name"] = results["Company Name"].fillna(
        results["Symbol"].str.removesuffix(".NS")
    )
    results["Market Cap"] = results["Market Cap"].div(1_000_000).map(
        lambda value: f"{value:,.0f} M" if pd.notna(value) else None
    )

    return results


def _format_value(value, format_string="{:.2f}", empty="Not available"):
    """Format optional numerical values consistently for the details panel."""
    return empty if pd.isna(value) else format_string.format(value)


def _format_text(value, empty="Not available"):
    """Use a readable fallback for missing text values."""
    return empty if value is None or pd.isna(value) else value


def _format_market_cap(value):
    """Format market capitalisation in millions, matching the results table."""
    return "Not available" if pd.isna(value) else f"{value / 1_000_000:,.0f} M"


def _price_at_cross(chart_data, cross_date):
    """Return the close on the recorded Golden Cross date, if it is present."""
    if cross_date is None or pd.isna(cross_date):
        return None
    matching_rows = chart_data.loc[chart_data.index == pd.Timestamp(cross_date)]
    if matching_rows.empty:
        return None
    return matching_rows.iloc[0]["Close"]


def _performance(chart_data, cross_close):
    """Calculate recent trading-session returns and the return since the cross."""
    latest_close = chart_data["Close"].iloc[-1]
    periods = (("1 Week", 5), ("1 Month", 21), ("3 Months", 63))
    values = []
    for label, sessions in periods:
        if len(chart_data) > sessions:
            base_close = chart_data["Close"].iloc[-(sessions + 1)]
            values.append((label, ((latest_close / base_close) - 1) * 100))
        else:
            values.append((label, None))
    since_cross = None if cross_close in (None, 0) else ((latest_close / cross_close) - 1) * 100
    values.append(("Since Golden Cross", since_cross))
    return values


def _has_death_cross_after(chart_data, cross_date):
    """Identify a bearish MA crossover after the displayed Golden Cross."""
    if cross_date is None or pd.isna(cross_date):
        return False
    after_cross = chart_data.loc[chart_data.index > pd.Timestamp(cross_date)]
    death_crosses = (
        (after_cross["MA_SHORT"].shift(1) >= after_cross["MA_LONG"].shift(1))
        & (after_cross["MA_SHORT"] < after_cross["MA_LONG"])
    )
    return bool(death_crosses.any())


def _render_stock_overview(result):
    """Render company information available from the scan's fundamentals lookup."""
    st.subheader("Company overview")
    overview = pd.DataFrame(
        {
            "Field": (
                "Symbol", "Company", "Sector", "Industry", "Market Cap", "PE", "PE Source", "EPS",
                "Weighted Industry P/E", "Median Industry P/E", "Industry Peers",
            ),
            "Value": (
                result["symbol"],
                _format_text(result.get("company_name"), result["symbol"].removesuffix(".NS")),
                _format_text(result.get("sector")),
                _format_text(result.get("industry")),
                _format_market_cap(result.get("market_cap")),
                _format_value(result.get("pe")),
                _format_text(result.get("pe_source")),
                _format_value(result.get("eps")),
                _format_value(result.get("industry_weighted_pe")),
                _format_value(result.get("industry_median_pe")),
                _format_value(result.get("industry_peer_count"), "{:.0f}"),
            ),
        }
    )
    st.dataframe(overview, width="stretch", hide_index=True)


def _render_technical_status(result, chart_data, cross_close):
    """Render current price/MA state and the Golden Cross facts."""
    st.subheader("Technical status")
    latest = chart_data.iloc[-1]
    columns = st.columns(4)
    columns[0].metric("Current Close", _format_value(latest["Close"]))
    columns[1].metric("Short MA", _format_value(latest["MA_SHORT"]))
    columns[2].metric("Long MA", _format_value(latest["MA_LONG"]))
    columns[3].metric("Golden Cross Close", _format_value(cross_close))

    cross_date = result.get("cross_date")
    cross_text = cross_date.strftime("%d %b %Y") if pd.notna(cross_date) else "Not available"
    status = pd.DataFrame(
        {
            "Check": (
                "Short MA 5-Day Slope", "Golden Cross Date", "Golden Cross Age",
                "52-Week Long MA High", "Long MA High Age", "Long MA Trough",
                "Long MA Decline Duration", "Long MA Decline to Trough", "Post-Trough 5-Day Long MA Slope",
                "Price Above Long MA",
            ),
            "Status": (
                _format_value(result.get("short_ma_slope"), "{:.4f}"),
                cross_text,
                f"{result.get('days_since_cross')} calendar days" if pd.notna(result.get("days_since_cross")) else "Not available",
                _format_value(result.get("long_ma_52_week_peak")),
                f"{result.get('long_ma_peak_age')} trading sessions" if pd.notna(result.get("long_ma_peak_age")) else "Not available",
                _format_value(result.get("long_ma_trough")),
                f"{result.get('long_ma_decline_duration')} trading sessions" if pd.notna(result.get("long_ma_decline_duration")) else "Not available",
                _format_value(result.get("long_ma_decline_percent"), "{:.2f}%"),
                _format_value(result.get("long_ma_recovery_slope"), "{:.4f}"),
                _format_value(result.get("price_above_long_ma_percent"), "{:.2f}%"),
            ),
        }
    )
    st.dataframe(status, width="stretch", hide_index=True)


def _render_score_breakdown(result):
    """Show the score composition only for the selected stock."""
    st.subheader("Score breakdown")
    st.caption("Total score ranks stocks that already passed the selected qualification checks.")
    score_data = pd.DataFrame(
        [(label, result.get(field, 0)) for field, label in SCORE_COMPONENTS],
        columns=("Component", "Points"),
    )
    total = result.get("score", 0)
    st.metric("Total Score", f"{total:.0f} / 85")
    st.dataframe(score_data, width="stretch", hide_index=True)


def _render_performance(chart_data, cross_close):
    """Render recent and since-cross price returns."""
    st.subheader("Recent performance")
    columns = st.columns(4)
    for column, (label, value) in zip(columns, _performance(chart_data, cross_close)):
        column.metric(label, _format_value(value, "{:+.2f}%"))


@st.cache_data(show_spinner=False, ttl=900, max_entries=128)
def _load_selected_history(
    symbol,
    source,
    adjusted_prices,
    snapshot_version,
    project_root,
):
    """Cache only one stock's chart rows, keyed by snapshot version."""
    del snapshot_version  # The value participates in Streamlit's cache key.
    services = build_data_services(source, Path(project_root))
    batch_data = services.history.download_batch(
        [symbol],
        years=1,
        adjusted_prices=adjusted_prices,
    )
    return services.history.get_symbol_history(batch_data, symbol)


def render_selected_stock(result, settings):
    """Load and render the selected stock's cached one-year details."""
    symbol = result["symbol"]
    source = settings.get("market_data_source", LIVE_SOURCE)
    snapshot = settings.get("market_data_snapshot", {})
    snapshot_version = snapshot.get("generated_at") or snapshot.get(
        "last_trading_date", "live"
    )
    project_root = Path(__file__).resolve().parents[1]

    with st.spinner(f"Loading one-year chart for {symbol}..."):
        history = _load_selected_history(
            symbol,
            source,
            settings["adjusted_prices"],
            snapshot_version,
            str(project_root),
        )

    if history.empty:
        st.error(f"Could not load one-year price history for {symbol}.")
        return

    chart_data = Indicators.add_moving_averages(
        history,
        settings["short_ma"],
        settings["long_ma"],
    )
    _render_stock_overview(result)
    st.subheader("One-year price and moving averages")
    render_stock_detail(symbol, chart_data, result["cross_date"])
    cross_close = _price_at_cross(chart_data, result.get("cross_date"))
    _render_technical_status(result, chart_data, cross_close)
    with st.expander("Show individual score details"):
        _render_score_breakdown(result)
    _render_performance(chart_data, cross_close)


def _render_data_provenance(settings, metrics):
    """Show auditable evidence of which provider served the completed scan."""
    requested_source = settings.get("market_data_source", LIVE_SOURCE)
    market_metrics = metrics.get("market_data", {})
    timing = metrics.get("timing", {})
    snapshot_metadata = settings.get("market_data_snapshot", {})
    fundamentals_coverage = snapshot_metadata.get("fundamentals_coverage", {})

    if requested_source == SNAPSHOT_SOURCE:
        fallback_requests = market_metrics.get("fallback_requests", 0)
        snapshot_hits = market_metrics.get("snapshot_hits", 0)
        if snapshot_hits and not fallback_requests:
            effective_source = "Git snapshot only"
            st.success("Data-source verification: price history came from the Git snapshot; Yahoo fallback was not used.")
        elif fallback_requests:
            effective_source = "Git snapshot + Yahoo fallback"
            st.warning(
                f"Data-source verification: Yahoo fallback was used for {fallback_requests} missing-data batch(es)."
            )
        else:
            effective_source = "Git snapshot (no completed history request)"
    else:
        effective_source = "Live Yahoo Finance"
        st.info("Data-source verification: this scan requested live Yahoo Finance history.")

    yahoo_calls = (
        market_metrics.get("requests", 0)
        if requested_source == LIVE_SOURCE
        else market_metrics.get("fallback_requests", 0)
    )
    columns = st.columns(4)
    columns[0].metric("Effective data source", effective_source)
    columns[1].metric(
        "Snapshot through",
        snapshot_metadata.get("last_trading_date", "Not applicable"),
    )
    columns[2].metric("Yahoo history calls", yahoo_calls)
    columns[3].metric("Total scan time", f"{timing.get('total_seconds', 0):.1f} sec")

    with st.expander("Data-source and timing details"):
        details = pd.DataFrame(
            {
                "Metric": (
                    "Selected source",
                    "Effective source",
                    "Local snapshot hits",
                    "Yahoo fallback batches",
                    "History loading time",
                    "Rule evaluation time",
                    "Stocks with PE",
                    "Stocks with industry classification",
                    "Industries with PE benchmarks",
                ),
                "Value": (
                    requested_source,
                    effective_source,
                    market_metrics.get("snapshot_hits", 0),
                    market_metrics.get("fallback_requests", 0),
                    f"{timing.get('data_load_seconds', 0):.2f} seconds",
                    f"{timing.get('rule_evaluation_seconds', 0):.2f} seconds",
                    fundamentals_coverage.get("pe", "Not reported"),
                    fundamentals_coverage.get("industry", "Not reported"),
                    fundamentals_coverage.get(
                        "industries_with_valuations", "Not reported"
                    ),
                ),
            }
        )
        st.dataframe(details, width="stretch", hide_index=True)


def render_results(df, scan_time, settings, metrics=None):
    """Render formatted qualified-stock results for a completed scan."""
    st.subheader("Qualified Stocks")
    st.caption(f"Latest scan: {scan_time:%d %b %Y, %I:%M %p}")
    _render_data_provenance(settings, metrics or {})

    if df.empty:
        st.warning("No qualifying stocks found.")
        return

    results = prepare_results(df)
    left, right = st.columns(2)
    left.metric("Qualified stocks", len(results))
    right.metric("Average score", f"{results['Score'].mean():.1f}")

    st.caption(
        "Score is out of 85. Select a stock to view its one-year chart, "
        "technical details, performance, and score breakdown."
    )
    selection = st.dataframe(
        results,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Score": st.column_config.NumberColumn(format="%d"),
            "Market Cap": st.column_config.TextColumn(),
            "Close": st.column_config.NumberColumn(format="%.2f"),
            "PE": st.column_config.NumberColumn(format="%.2f"),
            "EPS": st.column_config.NumberColumn(format="%.2f"),
            "Short MA": st.column_config.NumberColumn(format="%.2f"),
            "Long MA": st.column_config.NumberColumn(format="%.2f"),
            "Cross Date": st.column_config.DatetimeColumn(format="DD MMM YYYY"),
        },
    )

    selected_rows = selection.selection.rows
    if selected_rows:
        selected_result = df.iloc[selected_rows[0]]
        st.divider()
        render_selected_stock(selected_result, settings)


def render_optional_failures(df):
    """Show stocks rejected only because of selected optional checks."""
    if "check_type" in df.columns:
        optional_failures = df.loc[df["check_type"] == "optional"].copy()
    else:
        optional_failures = df.iloc[0:0].copy()

    st.subheader("Optional-check rejections")
    if optional_failures.empty:
        st.success("No stocks were rejected by the selected optional checks.")
        return

    optional_failures = optional_failures.rename(
        columns={
            "symbol": "Symbol",
            "stage": "Stage",
            "reason": "Reason",
        }
    )
    st.dataframe(
        optional_failures[["Symbol", "Stage", "Reason"]],
        width="stretch",
        hide_index=True,
    )
