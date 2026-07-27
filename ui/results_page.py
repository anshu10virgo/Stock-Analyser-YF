import os
from pathlib import Path

import pandas as pd
import streamlit as st

from core.indicators import Indicators
from providers.repository_data import SnapshotUnavailableError
from services.data_source import LIVE_SOURCE, SNAPSHOT_SOURCE, build_data_services
from services.scan_report import (
    MailConfiguration,
    build_chart_archives,
    build_messages,
    build_price_chart_png,
    build_workbook,
    parse_recipients,
    send_messages,
)
from ui.stock_detail import render_pe_eps_chart, render_stock_detail


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
    "optional_filters_not_evaluated": "Optional Data",
}

IMPENDING_DISPLAY_COLUMNS = {
    "symbol": "Symbol",
    "company_name": "Company Name",
    "sector": "Sector",
    "industry": "Industry",
    "market_cap": "Market Cap",
    "close": "Close",
    "pe": "PE",
    "eps": "EPS",
    "ma_short": "Short MA",
    "ma_long": "Long MA",
    "impending_gap_percent": "MA Gap %",
    "short_ma_slope": "Short MA 5-Day Slope",
    "long_ma_slope": "Long MA 5-Day Slope",
    "optional_filters_not_evaluated": "Optional Data",
}


SCORE_COMPONENTS = (
    ("score_cross", "Golden Cross Timing"),
    ("score_slope", "Long-term Trend"),
    ("score_distance", "Price Position"),
    ("score_pe", "PE"),
    ("score_eps", "EPS"),
    ("score_market_cap", "Market Capitalisation"),
)


def prepare_results(df, impending=False):
    """Return scanner results with user-friendly labels and values."""
    columns = IMPENDING_DISPLAY_COLUMNS if impending else DISPLAY_COLUMNS
    results = df.reindex(columns=columns).rename(columns=columns)

    results["Company Name"] = results["Company Name"].fillna(
        results["Symbol"].str.removesuffix(".NS")
    )
    results["Market Cap"] = results["Market Cap"].div(10_000_000).map(
        lambda value: f"₹{value:,.0f} Cr" if pd.notna(value) else None
    )
    results["Optional Data"] = results["Optional Data"].map(
        lambda filters: (
            "Not evaluated: " + ", ".join(filters)
            if isinstance(filters, (list, tuple)) and filters
            else None
        )
    )
    if results["Optional Data"].isna().all():
        results.drop(columns=["Optional Data"], inplace=True)

    return results


def _format_value(value, format_string="{:.2f}", empty="Not available"):
    """Format optional numerical values consistently for the details panel."""
    return empty if pd.isna(value) else format_string.format(value)


def _format_text(value, empty="Not available"):
    """Use a readable fallback for missing text values."""
    return empty if value is None or pd.isna(value) else value


def _format_market_cap(value):
    """Format Indian market capitalisation in crore."""
    return "Not available" if pd.isna(value) else f"₹{value / 10_000_000:,.0f} Cr"


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


def _peg_ratio(result, screener_summary):
    """Calculate the displayed PEG using current P/E and stored 3Y profit growth."""
    pe = result.get("pe")
    growth = screener_summary.get("profit_growth_3y")
    if pd.isna(pe) or pd.isna(growth) or pe <= 0 or growth <= 0:
        return None
    return pe / growth


def _render_stock_overview(result, screener_summary):
    """Render company and valuation information from committed snapshots."""
    st.subheader("Company overview")
    overview = pd.DataFrame(
        {
            "Field": (
                "Symbol", "Company", "Sector", "Industry", "Market Cap", "PE", "EPS",
                "Debt-to-Equity Ratio", "ROE (%)", "PEG Ratio",
                "Weighted Industry P/E", "Median Industry P/E", "Industry Peers",
                "Optional filters not evaluated",
            ),
            "Value": (
                result["symbol"],
                _format_text(result.get("company_name"), result["symbol"].removesuffix(".NS")),
                _format_text(result.get("sector")),
                _format_text(result.get("industry")),
                _format_market_cap(result.get("market_cap")),
                _format_value(result.get("pe")),
                _format_value(result.get("eps")),
                _format_value(screener_summary.get("debt_to_equity")),
                _format_value(screener_summary.get("roe"), "{:.2f}%"),
                _format_value(_peg_ratio(result, screener_summary)),
                _format_value(result.get("industry_weighted_pe")),
                _format_value(result.get("industry_median_pe")),
                _format_value(result.get("industry_peer_count"), "{:.0f}"),
                (
                    ", ".join(result.get("optional_filters_not_evaluated", []))
                    or "None"
                ),
            ),
        }
    )
    st.dataframe(overview, width="stretch", hide_index=True)


def _render_growth_cards(screener_summary):
    """Render the requested three-year growth metrics outside the overview table."""
    st.subheader("Three-year growth")
    columns = st.columns(3)
    metrics = (
        ("Profit Growth CAGR — 3Y", "profit_growth_3y"),
        ("EPS Growth CAGR — 3Y", "eps_growth_3y"),
        ("Revenue Growth CAGR — 3Y", "sales_growth_3y"),
    )
    for column, (label, field) in zip(columns, metrics):
        column.metric(
            label,
            _format_value(screener_summary.get(field), "{:+.2f}%"),
        )


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
    if result.get("strategy") == "Impending Golden Cross":
        impending_status = pd.DataFrame(
            {
                "Check": (
                    "Current Short-to-Long MA Gap",
                    "Latest 5-Day Long MA Slope",
                    "Validated Pre-Cross Period",
                ),
                "Status": (
                    _format_value(result.get("impending_gap_percent"), "{:.2f}%"),
                    _format_value(result.get("long_ma_slope"), "{:.4f}"),
                    f"{result.get('pre_cross_validation_sessions')} trading sessions",
                ),
            }
        )
        st.dataframe(impending_status, width="stretch", hide_index=True)


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
    history_years,
    snapshot_version,
    project_root,
):
    """Cache one stock's full retained chart history by snapshot version."""
    del snapshot_version  # The value participates in Streamlit's cache key.
    services = build_data_services(source, Path(project_root))
    batch_data = services.history.download_batch(
        [symbol],
        years=history_years,
        adjusted_prices=adjusted_prices,
    )
    return services.history.get_symbol_history(batch_data, symbol)


@st.cache_data(show_spinner=False, max_entries=128)
def _load_selected_valuation(
    symbol,
    screener_snapshot_version,
    project_root,
):
    """Load one symbol from the committed Screener snapshot only."""
    del screener_snapshot_version  # The value participates in the cache key.
    services = build_data_services(LIVE_SOURCE, Path(project_root))
    history = services.screener.valuation_history(symbol)
    summary = services.screener.fundamental_metrics(symbol)
    return history, summary


def render_selected_stock(result, settings, show_score=True):
    """Load and render the selected stock's cached full-history details."""
    symbol = result["symbol"]
    source = settings.get("market_data_source", LIVE_SOURCE)
    snapshot = settings.get("market_data_snapshot", {})
    snapshot_version = snapshot.get("generated_at") or snapshot.get(
        "last_trading_date", "live"
    )
    history_years = int(snapshot.get("retention_calendar_years") or 10)
    project_root = Path(__file__).resolve().parents[1]

    with st.spinner(f"Loading available price history for {symbol}..."):
        history = _load_selected_history(
            symbol,
            source,
            settings["adjusted_prices"],
            history_years,
            snapshot_version,
            str(project_root),
        )

    if history.empty:
        st.error(f"Could not load price history for {symbol}.")
        return

    chart_data = Indicators.add_moving_averages(
        history,
        settings["short_ma"],
        settings["long_ma"],
    )
    screener_services = build_data_services(LIVE_SOURCE, project_root)
    screener_metadata = screener_services.screener.metadata()
    valuation_history = pd.DataFrame()
    screener_summary = {}
    try:
        valuation_history, screener_summary = _load_selected_valuation(
            symbol,
            screener_metadata.get("generated_at", "missing"),
            str(project_root),
        )
    except SnapshotUnavailableError:
        pass

    _render_stock_overview(result, screener_summary)
    _render_growth_cards(screener_summary)
    st.subheader("Price and moving averages")
    st.caption(
        "Use the period buttons, range slider, drag-to-zoom, pan, or reset "
        "controls to explore all available history."
    )
    render_stock_detail(symbol, chart_data, result["cross_date"])
    if not valuation_history.empty:
        render_pe_eps_chart(
            symbol,
            valuation_history,
            screener_summary.get("source_url"),
            screener_summary.get("refreshed_at"),
        )
    else:
        st.info(
            "Historical P/E and TTM EPS will appear after the committed "
            "Screener fundamentals snapshot is refreshed."
        )
    cross_close = _price_at_cross(chart_data, result.get("cross_date"))
    _render_technical_status(result, chart_data, cross_close)
    if show_score:
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


def _render_impending_results(df, settings):
    """Render the separately ranked proximity view for impending crosses."""
    st.subheader("Impending Golden Cross")
    if df.empty:
        st.warning("No impending Golden Cross stocks found.")
        return

    results = prepare_results(df, impending=True)
    st.metric("Impending stocks", len(results))
    st.caption(
        "Ordered by the smallest moving-average gap, then the strongest "
        "Short-MA slope. These stocks are not assigned a Post-Cross score."
    )
    selection = st.dataframe(
        results,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Market Cap": st.column_config.TextColumn(),
            "Close": st.column_config.NumberColumn(format="%.2f"),
            "PE": st.column_config.NumberColumn(format="%.2f"),
            "EPS": st.column_config.NumberColumn(format="%.2f"),
            "Short MA": st.column_config.NumberColumn(format="%.2f"),
            "Long MA": st.column_config.NumberColumn(format="%.2f"),
            "MA Gap %": st.column_config.NumberColumn(format="%.2f%%"),
            "Short MA 5-Day Slope": st.column_config.NumberColumn(format="%.4f"),
            "Long MA 5-Day Slope": st.column_config.NumberColumn(format="%.4f"),
        },
        key="impending_results_table",
    )
    if selection.selection.rows:
        st.divider()
        render_selected_stock(
            df.iloc[selection.selection.rows[0]], settings, show_score=False
        )


def _mail_credentials():
    """Read report credentials from Streamlit secrets or local environment."""
    try:
        username = st.secrets.get("REPORT_SMTP_USERNAME")
        password = st.secrets.get("REPORT_SMTP_APP_PASSWORD")
    except (FileNotFoundError, KeyError):
        username = None
        password = None
    username = username or os.environ.get("REPORT_SMTP_USERNAME")
    password = password or os.environ.get("REPORT_SMTP_APP_PASSWORD")
    if not username or not password:
        return None
    return MailConfiguration(username=username, password=password)


def _report_chart_images(post_cross, impending, settings, progress):
    """Build maximum-period chart PNGs from the selected market-data policy."""
    combined = pd.concat([post_cross, impending], ignore_index=True)
    if combined.empty:
        return []
    combined = combined.drop_duplicates("symbol", keep="first")
    records = combined.set_index("symbol").to_dict("index")
    symbols = list(records)
    services = build_data_services(
        settings.get("market_data_source", LIVE_SOURCE),
        Path(__file__).resolve().parents[1],
    )
    history_years = int(
        settings.get("market_data_snapshot", {}).get("retention_calendar_years")
        or 10
    )
    images = []
    processed = 0
    for offset in range(0, len(symbols), 10):
        chunk = symbols[offset : offset + 10]
        batch = services.history.download_batch(
            chunk,
            years=history_years,
            adjusted_prices=settings.get("adjusted_prices", False),
        )
        for symbol in chunk:
            history = services.history.get_symbol_history(batch, symbol)
            if history.empty:
                processed += 1
                progress.progress(processed / len(symbols))
                continue
            chart_data = Indicators.add_moving_averages(
                history,
                settings["short_ma"],
                settings["long_ma"],
            )
            payload = build_price_chart_png(
                symbol,
                chart_data,
                records[symbol].get("cross_date"),
            )
            images.append((f"{symbol.removesuffix('.NS')}_price_chart.png", payload))
            processed += 1
            progress.progress(processed / len(symbols))
    return images


def _render_email_report(post_cross, impending, scan_time, settings):
    """Render the explicit, session-only scan report delivery action."""
    st.divider()
    st.subheader("Email scan report")
    st.caption(
        "Send both result lists, the applied filters, and maximum-period "
        "price/MA chart snapshots. Recipient addresses are not saved."
    )
    with st.form("email_scan_report"):
        raw_recipients = st.text_input(
            "Recipient email addresses",
            placeholder="name@example.com, another@example.com",
            help="Separate multiple addresses with commas.",
        )
        submitted = st.form_submit_button(
            "Email Report",
            type="primary",
            disabled=post_cross.empty and impending.empty,
        )
    if not submitted:
        return

    try:
        recipients = parse_recipients(raw_recipients)
    except ValueError as error:
        st.error(str(error))
        return
    credentials = _mail_credentials()
    if credentials is None:
        st.error(
            "Email is not configured. Add REPORT_SMTP_USERNAME and "
            "REPORT_SMTP_APP_PASSWORD to Streamlit Secrets."
        )
        return

    status = st.status("Preparing report...", expanded=True)
    try:
        status.write("Building the filters-first Excel workbook...")
        workbook = build_workbook(settings, scan_time, post_cross, impending)
        status.write("Rendering maximum-period price charts...")
        progress = st.progress(0)
        chart_images = _report_chart_images(
            post_cross,
            impending,
            settings,
            progress,
        )
        archives = build_chart_archives(chart_images)
        status.write(
            f"Sending {max(1, len(archives))} email part(s) to "
            f"{len(recipients)} recipient(s)..."
        )
        messages = build_messages(
            recipients,
            credentials.username,
            scan_time,
            len(post_cross),
            len(impending),
            workbook,
            archives,
        )
        send_messages(messages, credentials)
    except Exception as error:
        status.update(label="Email report failed", state="error", expanded=True)
        st.error(f"The report could not be sent: {error}")
        return
    status.update(label="Email report sent", state="complete", expanded=False)
    st.success(
        f"Sent {len(messages)} report email(s) to {', '.join(recipients)}."
    )


def render_results(df, impending_df, scan_time, settings, metrics=None):
    """Render formatted qualified-stock results for a completed scan."""
    st.subheader("Scan Results")
    st.caption(f"Latest scan: {scan_time:%d %b %Y, %I:%M %p}")
    _render_data_provenance(settings, metrics or {})

    st.subheader("Post Golden Cross")
    if df.empty:
        st.warning("No Post Golden Cross stocks found.")
    else:
        results = prepare_results(df)
        left, right = st.columns(2)
        left.metric("Post-Cross stocks", len(results))
        right.metric("Average score", f"{results['Score'].mean():.1f}")

        st.caption(
            "Score is out of 85. Select a stock to view its price chart, "
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
            key="post_cross_results_table",
        )

        if selection.selection.rows:
            selected_result = df.iloc[selection.selection.rows[0]]
            st.divider()
            render_selected_stock(selected_result, settings)

    if settings.get("include_impending_crosses"):
        st.divider()
        _render_impending_results(impending_df, settings)
    _render_email_report(df, impending_df, scan_time, settings)


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
