import plotly.graph_objects as go
import pandas as pd
import streamlit as st


def render_stock_detail(
    symbol,
    df,
    cross_date=None,
    trough_dates=None
):

    st.subheader(symbol)

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MA_SHORT"],
            name="Short MA"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MA_LONG"],
            name="Long MA"
        )
    )

    if cross_date is not None and pd.notna(cross_date):

        fig.add_vline(
            x=cross_date,
            line_width=2,
            line_dash="dash",
            annotation_text=(
                f"Golden Cross: {cross_date:%d %b %Y}"
            ),
            annotation_position="top left",
        )

    if trough_dates:

        for date in trough_dates:

            fig.add_vline(
                x=date,
                line_width=1
            )

    fig.update_layout(
        height=700
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )
