"""Backtester workflow page."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stock_analyser.infrastructure.data_services import LIVE_SOURCE, build_data_services
from stock_analyser.infrastructure.local.stock_universe import StockUniverse
from stock_analyser.infrastructure.r2 import config as storage_config
from stock_analyser.infrastructure.r2.storage import ScopedSnapshotStorage
from stock_analyser.application.commands.run_backtest import RunBacktestCommand
from stock_analyser.application.workflows.backtest_workflow import BacktestWorkflow
from stock_analyser.domain.backtesting import summarize_returns
from stock_analyser.presentation.streamlit.components.stock_detail import PRICE_RANGE_BUTTONS
from stock_analyser.presentation.streamlit.configuration import build_backtest_config
from stock_analyser.presentation.streamlit.session_adapter import current_session


def render_backtester_page(project_root) -> None:
    session = current_session()
    symbols = session.get("selected_symbols", [])
    if not symbols:
        st.info("Complete Setup before running a backtest.")
        return
    config = build_backtest_config(session.get("backtest_settings"))
    universe = StockUniverse(
        project_root / "data" / "stock_universe",
        storage=ScopedSnapshotStorage(
            storage_config.application_snapshot_storage(project_root),
            "data/stock_universe",
        ),
    )
    names = {}
    try:
        universe_frame = pd.read_csv(universe.active_file())
        names = universe_frame.set_index("Symbol")["Company Name"].dropna().to_dict()
    except (OSError, KeyError, pd.errors.ParserError):
        pass
    st.subheader("Backtester")
    st.caption("Replay your Post Golden Cross strategy against historical prices.")
    request = session.pop("ticksy_backtest_request", None) or {}
    requested_symbols = [symbol for symbol in request.get("symbols", []) if symbol in symbols]
    with st.container(border=True):
        st.subheader("Strategy summary")
        summary = st.columns(3)
        summary[0].caption(f"**Moving averages**  {config.short_ma} / {config.long_ma}")
        summary[1].caption(f"**Cross age**  {config.max_cross_age} days")
        summary[2].caption("**Short-MA slope**  Positive, 5 sessions")
        summary[0].caption(f"**Long-MA decline**  ≥{config.min_long_ma_decline}%")
        summary[1].caption(f"**Decline duration**  ≥{config.min_long_ma_decline_duration} sessions")
        summary[2].caption("**Long-MA recovery**  Positive")
        summary[0].caption("**Price position**  Close above Long MA")
        summary[1].caption(f"**Maximum premium**  {config.max_price_premium}%")
        summary[2].caption("**Price data**  Unadjusted")
    selected = st.multiselect("Stocks to backtest", symbols, default=[], format_func=lambda symbol: f"{symbol} — {names.get(symbol, symbol)}", placeholder="Type to filter ticker or company")
    period = st.radio("Test period", ("1Y", "3Y", "5Y", "10Y"), horizontal=True, index=3)
    if requested_symbols:
        selected = requested_symbols
        period = request.get("period", period)
    if st.button("Run Backtest", type="primary", disabled=not selected) or bool(requested_symbols):
        services = build_data_services(
            session.get("selected_market_data_source", LIVE_SOURCE), project_root
        )
        years = int(period[:-1])
        execution = BacktestWorkflow(services).execute(
            RunBacktestCommand(tuple(selected), years, config, names)
        )
        session["backtest_results"] = execution.results
        session["backtest_charts"] = execution.charts
        session["backtest_one_year_summary"] = execution.one_year_summary
    results = session.get("backtest_results")
    if results is not None:
        st.subheader("Historical results")
        if results.empty:
            st.warning("No historical signals qualified for the selected stocks and period.")
        else:
            summary = session.get("backtest_one_year_summary") or summarize_returns(
                results["1Y"], signal_count=len(results)
            )
            metrics = st.columns(4)
            metrics[0].metric("Signals", summary.signal_count)
            metrics[1].metric("Signals with 1Y data", summary.observed_count)
            average = summary.average_return
            median = summary.median_return
            metrics[2].metric("Average 1Y return", f"{average:+.1f}%" if average is not None else "N/A")
            metrics[3].metric("Median 1Y return", f"{median:+.1f}%" if median is not None else "N/A")
            formats = {"Cross date": st.column_config.DateColumn(format="DD MMM YYYY"), "Signal date": st.column_config.DateColumn(format="DD MMM YYYY"), "Entry": st.column_config.NumberColumn(format="%.2f"), "P/E": st.column_config.NumberColumn(format="%.2f")}
            formats.update({horizon: st.column_config.NumberColumn(format="%.2f%%") for horizon in ("1W", "2W", "3W", "1M", "3M", "6M", "1Y")})
            st.dataframe(results, width="stretch", hide_index=True, column_config=formats)
            with st.expander("Show stock chart"):
                chart_symbol = st.selectbox("Stock chart", sorted(results["Stock"].unique()))
                chart_data = session.get("backtest_charts", {}).get(chart_symbol)
                if chart_data is not None and not chart_data.empty:
                    figure = go.Figure()
                    for column, label, colour in (("Close", "Close", "#26324B"), ("MA_SHORT", f"Short MA {config.short_ma}", "#16A085"), ("MA_LONG", f"Long MA {config.long_ma}", "#E67E22")):
                        figure.add_scatter(x=chart_data.index, y=chart_data[column], name=label, line={"color": colour})
                    signals = results.loc[results["Stock"].eq(chart_symbol)]
                    figure.add_scatter(x=signals["Signal date"], y=[chart_data.loc[:pd.Timestamp(date), "Close"].iloc[-1] for date in signals["Signal date"]], name="Signals", mode="markers", marker={"color": "white", "line": {"color": "#26324B", "width": 2}, "size": 10})
                    figure.update_layout(
                        height=600,
                        dragmode="zoom",
                        hovermode="x unified",
                        margin={"l": 10, "r": 10, "t": 50, "b": 10},
                        paper_bgcolor="#F8FAFC",
                        plot_bgcolor="#F8FAFC",
                        xaxis={
                            "rangeslider": {"visible": True, "thickness": 0.08},
                            "rangeselector": {"buttons": list(PRICE_RANGE_BUTTONS), "x": 0, "y": 1.08},
                            "showspikes": True,
                            "spikemode": "across",
                        },
                        yaxis={"fixedrange": False},
                    )
                    st.plotly_chart(figure, width="stretch", config={"displaylogo": False, "scrollZoom": True})
            st.caption("Historical, hypothetical results — not investment advice.")
