"""Backtester workflow page."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.indicators import Indicators
from models.scan_config import ScanConfig
from services.backtest_service import BacktestService
from services.data_source import LIVE_SOURCE, build_data_services


def _config(settings: dict | None) -> ScanConfig:
    settings = settings or {}
    return ScanConfig(
        settings.get("short_ma", 50), settings.get("long_ma", 200),
        settings.get("cross_age", 80), settings.get("min_long_ma_decline_duration", 60),
        settings.get("min_long_ma_decline", 10), settings.get("max_price_premium", 10),
        adjusted_prices=False,
    )


def render_backtester_page(project_root) -> None:
    symbols = st.session_state.get("selected_symbols", [])
    if not symbols:
        st.info("Complete Setup before running a backtest.")
        return
    config = _config(st.session_state.get("backtest_settings"))
    st.subheader("Backtester")
    st.caption("Replay your Post Golden Cross strategy against historical prices.")
    st.info(f"Strategy summary: {config.short_ma} / {config.long_ma} MA · Cross age: {config.max_cross_age} days · Positive 5-session Short-MA slope · Long-MA decline ≥{config.min_long_ma_decline}% for ≥{config.min_long_ma_decline_duration} sessions · Positive recovery · Close above Long MA · Max premium {config.max_price_premium}% · Unadjusted prices")
    selected = st.multiselect("Stocks to backtest", symbols, default=symbols[:1], placeholder="Type to filter ticker")
    period = st.radio("Test period", ("1Y", "3Y", "5Y", "10Y"), horizontal=True, index=3)
    if not st.button("Run Backtest", type="primary", disabled=not selected):
        services = build_data_services(LIVE_SOURCE, project_root)
        years = int(period[:-1])
        batch = services.history.download_batch(selected, years=years + 2, adjusted_prices=False)
        engine = BacktestService(config, services.screener)
        rows = []
        charts = {}
        for symbol in selected:
            history = services.history.get_symbol_history(batch, symbol)
            charts[symbol] = Indicators.add_moving_averages(history, config.short_ma, config.long_ma)
            run = engine.replay_symbol(symbol, history)
            for signal in run.signals:
                pe_age = None if signal.pe_date is None else (signal.signal_date.date() - signal.pe_date.date()).days
                rows.append({"Stock": symbol, "Cross date": signal.cross_date, "Signal date": signal.signal_date, "Entry": signal.entry_price, "P/E": signal.pe, "P/E date": signal.pe_date, "P/E age": pe_age, **signal.returns})
        st.session_state["backtest_results"] = pd.DataFrame(rows)
        st.session_state["backtest_charts"] = charts
    results = st.session_state.get("backtest_results")
    if results is not None:
        st.subheader("Historical results")
        if results.empty:
            st.warning("No historical signals qualified for the selected stocks and period.")
        else:
            one_year = results["1Y"].dropna()
            metrics = st.columns(4)
            metrics[0].metric("Signals", len(results))
            metrics[1].metric("Signals with 1Y data", len(one_year))
            metrics[2].metric("Average 1Y return", f"{one_year.mean():+.1f}%" if not one_year.empty else "N/A")
            metrics[3].metric("Median 1Y return", f"{one_year.median():+.1f}%" if not one_year.empty else "N/A")
            st.dataframe(results, width="stretch", hide_index=True)
            chart_symbol = st.selectbox("Stock chart", sorted(results["Stock"].unique()))
            chart_data = st.session_state.get("backtest_charts", {}).get(chart_symbol)
            if chart_data is not None and not chart_data.empty:
                figure = go.Figure()
                for column, label, colour in (("Close", "Close", "#26324B"), ("MA_SHORT", f"Short MA {config.short_ma}", "#16A085"), ("MA_LONG", f"Long MA {config.long_ma}", "#E67E22")):
                    figure.add_scatter(x=chart_data.index, y=chart_data[column], name=label, line={"color": colour})
                signals = results.loc[results["Stock"].eq(chart_symbol)]
                figure.add_scatter(x=signals["Signal date"], y=[chart_data.loc[:date, "Close"].iloc[-1] for date in signals["Signal date"]], name="Signals", mode="markers", marker={"color": "white", "line": {"color": "#26324B", "width": 2}, "size": 10})
                figure.update_layout(height=380, margin={"l": 10, "r": 10, "t": 30, "b": 10}, paper_bgcolor="#F8FAFC", plot_bgcolor="#F8FAFC")
                st.plotly_chart(figure, width="stretch")
            st.caption("Historical, hypothetical results — not investment advice.")
