import pandas as pd
import streamlit as st

from core.data_loader import DataLoader
from core.indicators import Indicators
from ui.stock_detail import render_stock_detail


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


def render_selected_stock(result, settings):
    """Download and render one year of chart data for a selected result."""
    symbol = result["symbol"]

    with st.spinner(f"Loading one-year chart for {symbol}..."):
        batch_data = DataLoader.download_batch(
            [symbol],
            years=1,
            adjusted_prices=settings["adjusted_prices"],
        )
        history = DataLoader.get_symbol_history(batch_data, symbol)

    if history.empty:
        st.error(f"Could not load one-year price history for {symbol}.")
        return

    chart_data = Indicators.add_moving_averages(
        history,
        settings["short_ma"],
        settings["long_ma"],
    )
    render_stock_detail(symbol, chart_data, result["cross_date"])


def render_results(df, scan_time, settings):
    """Render formatted qualified-stock results for a completed scan."""
    st.subheader("Qualified Stocks")
    st.caption(f"Latest scan: {scan_time:%d %b %Y, %I:%M %p}")

    if df.empty:
        st.warning("No qualifying stocks found.")
        return

    results = prepare_results(df)
    left, right = st.columns(2)
    left.metric("Qualified stocks", len(results))
    right.metric("Average score", f"{results['Score'].mean():.1f}")

    st.caption("Click a stock row to view its one-year chart.")
    selection = st.dataframe(
        results,
        use_container_width=True,
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
