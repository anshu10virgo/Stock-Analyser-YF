import plotly.graph_objects as go
import pandas as pd
import streamlit as st


VALUATION_PERIOD_DAYS = {
    "1M": 30,
    "6M": 183,
    "1Y": 365,
    "3Y": 3 * 365,
    "5Y": 5 * 365,
    "10Y": 10 * 365,
}

PRICE_RANGE_BUTTONS = (
    {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
    {"count": 1, "label": "1Y", "step": "year", "stepmode": "backward"},
    {"count": 3, "label": "3Y", "step": "year", "stepmode": "backward"},
    {"count": 5, "label": "5Y", "step": "year", "stepmode": "backward"},
    {"count": 10, "label": "10Y", "step": "year", "stepmode": "backward"},
    {"label": "Max", "step": "all"},
)


def build_stock_detail_figure(symbol, df, cross_date=None, trough_dates=None):
    """Build the reusable full-history price and moving-average figure."""
    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price",
            hovertext=symbol,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MA_SHORT"],
            name="Short MA",
            hovertemplate="%{x|%d %b %Y}<br>Short MA: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MA_LONG"],
            name="Long MA",
            hovertemplate="%{x|%d %b %Y}<br>Long MA: %{y:.2f}<extra></extra>",
        )
    )

    if cross_date is not None and pd.notna(cross_date):
        fig.add_vline(
            x=cross_date,
            line_width=2,
            line_dash="dash",
            annotation_text=f"Golden Cross: {cross_date:%d %b %Y}",
            annotation_position="top left",
        )

    for date in trough_dates or ():
        fig.add_vline(x=date, line_width=1)

    fig.update_layout(
        height=700,
        dragmode="zoom",
        hovermode="x unified",
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        xaxis={
            "rangeslider": {"visible": True, "thickness": 0.08},
            "rangeselector": {
                "buttons": list(PRICE_RANGE_BUTTONS),
                "x": 0,
                "y": 1.08,
            },
            "showspikes": True,
            "spikemode": "across",
        },
        yaxis={"fixedrange": False},
    )
    return fig


def render_stock_detail(
    symbol,
    df,
    cross_date=None,
    trough_dates=None
):

    st.subheader(symbol)

    fig = build_stock_detail_figure(symbol, df, cross_date, trough_dates)

    st.plotly_chart(
        fig,
        width="stretch",
        config={
            "displaylogo": False,
            "scrollZoom": True,
            "modeBarButtonsToAdd": ["pan2d", "resetScale2d"],
        },
        key=f"price_ma_chart_{symbol}",
    )


def filter_valuation_history(history: pd.DataFrame, period: str) -> pd.DataFrame:
    """Restrict committed Screener observations to a selected chart period."""
    if period not in VALUATION_PERIOD_DAYS:
        raise ValueError(f"Unsupported valuation period: {period}")
    if history.empty:
        return history.copy()
    pe_dates = history.loc[history["pe"].notna(), "date"]
    if pe_dates.empty:
        return history.iloc[0:0].copy()
    cutoff = pe_dates.max() - pd.Timedelta(days=VALUATION_PERIOD_DAYS[period])
    return history.loc[history["date"].ge(cutoff)].copy()


def build_pe_eps_figure(history: pd.DataFrame) -> go.Figure:
    """Build a dual-axis P/E line, median reference, and TTM EPS bars."""
    pe = history.dropna(subset=["pe"])
    eps = history.dropna(subset=["ttm_eps"])
    median_pe = float(pe["pe"].median())

    figure = go.Figure()
    if not eps.empty:
        figure.add_trace(
            go.Bar(
                x=eps["date"],
                y=eps["ttm_eps"],
                name="TTM EPS",
                marker_color="rgba(112, 181, 229, 0.55)",
                yaxis="y",
                hovertemplate=(
                    "%{x|%d %b %Y}<br>TTM EPS: %{y:.2f}<extra></extra>"
                ),
                legendrank=3,
            )
        )
    figure.add_trace(
        go.Scatter(
            x=pe["date"],
            y=pe["pe"],
            name="P/E",
            mode="lines",
            line={"color": "#5D5FEF", "width": 2.5},
            yaxis="y2",
            hovertemplate="%{x|%d %b %Y}<br>P/E: %{y:.2f}<extra></extra>",
            legendrank=1,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=(pe["date"].min(), pe["date"].max()),
            y=(median_pe, median_pe),
            name=f"Median P/E = {median_pe:.1f}",
            mode="lines",
            line={"color": "#9EA4AF", "width": 1.5, "dash": "dash"},
            yaxis="y2",
            hovertemplate=f"Median P/E: {median_pe:.2f}<extra></extra>",
            legendrank=2,
        )
    )
    figure.update_layout(
        height=540,
        margin={"l": 10, "r": 10, "t": 15, "b": 10},
        hovermode="x unified",
        bargap=0.08,
        xaxis={
            "title": None,
            "showgrid": False,
            "rangeslider": {"visible": False},
        },
        yaxis={
            "title": "TTM EPS",
            "side": "left",
            "showgrid": True,
            "gridcolor": "rgba(128, 128, 128, 0.18)",
            "zeroline": False,
        },
        yaxis2={
            "title": "P/E",
            "side": "right",
            "overlaying": "y",
            "showgrid": False,
            "zeroline": False,
        },
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.14,
            "xanchor": "center",
            "x": 0.5,
            "traceorder": "normal",
        },
    )
    return figure


def render_pe_eps_chart(
    symbol: str,
    history: pd.DataFrame,
    source_url: str | None,
    refreshed_at: str | None,
) -> None:
    """Render committed historical valuation without making a live request."""
    st.subheader("Historical P/E and TTM EPS")
    period = st.segmented_control(
        "Historical valuation period",
        options=tuple(VALUATION_PERIOD_DAYS),
        default="5Y",
        key=f"valuation_period_{symbol}",
        label_visibility="collapsed",
    )
    selected = filter_valuation_history(history, period or "5Y")
    if selected["pe"].notna().sum() < 2:
        st.info(f"No historical P/E series is available for {symbol}.")
        return
    st.plotly_chart(
        build_pe_eps_figure(selected),
        width="stretch",
        key=f"pe_eps_chart_{symbol}",
    )
    source = (
        f"[Screener.in]({source_url})" if source_url else "Screener.in"
    )
    refresh_text = (
        pd.Timestamp(refreshed_at).strftime("%d %b %Y")
        if refreshed_at and pd.notna(pd.to_datetime(refreshed_at, errors="coerce"))
        else "not reported"
    )
    st.caption(
        f"Source: {source} · Snapshot refreshed {refresh_text}. "
        "TTM EPS changes when new financial results become available."
    )
