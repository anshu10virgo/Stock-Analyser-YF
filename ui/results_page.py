import streamlit as st


DISPLAY_COLUMNS = {
    "symbol": "Symbol",
    "company_name": "Company Name",
    "sector": "Sector",
    "industry": "Industry",
    "score": "Score",
    "market_cap": "Market Cap (M)",
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
    results["Market Cap (M)"] = results["Market Cap (M)"].div(1_000_000)

    return results


def render_results(df, scan_time):
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

    st.dataframe(
        results,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.NumberColumn(format="%d"),
            "Market Cap (M)": st.column_config.NumberColumn(format="%.2f"),
            "Close": st.column_config.NumberColumn(format="%.2f"),
            "PE": st.column_config.NumberColumn(format="%.2f"),
            "EPS": st.column_config.NumberColumn(format="%.2f"),
            "Short MA": st.column_config.NumberColumn(format="%.2f"),
            "Long MA": st.column_config.NumberColumn(format="%.2f"),
            "Cross Date": st.column_config.DatetimeColumn(format="DD MMM YYYY"),
        },
    )
