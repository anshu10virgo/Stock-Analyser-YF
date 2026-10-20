"""Progressive scan execution page."""

from datetime import datetime

import streamlit as st

from stock_analyser.infrastructure.data_services import build_data_services
from stock_analyser import PROJECT_ROOT
from stock_analyser.application.commands.run_scan import RunScanCommand
from stock_analyser.application.workflows.scan_workflow import ScanWorkflow
from stock_analyser.presentation.streamlit.components.results import prepare_results
from stock_analyser.presentation.streamlit.components.scan_insights import render_scan_insights
from stock_analyser.presentation.streamlit.components.theme import scroll_to_top
from stock_analyser.presentation.streamlit.configuration import build_scan_config
from stock_analyser.presentation.streamlit.navigation import navigate_to
from stock_analyser.presentation.streamlit.session_adapter import current_session


def _live_update(index: int, total: int, run, placeholders: dict) -> None:
    placeholders["progress"].progress(index / total)
    placeholders["processed"].metric("Processed", f"{index:,} / {total:,}")
    placeholders["qualified"].metric("Post Cross", f"{len(run.passed):,}")
    placeholders["impending"].metric("Impending", f"{len(run.impending):,}")
    placeholders["rejected"].metric("Rejected", f"{len(run.failed):,}")
    if index % 25 and index != total:
        return
    frames = run.as_dataframes()
    with placeholders["results"].container():
        st.subheader("Post Golden Cross stocks so far")
        if not frames["passed"].empty:
            st.dataframe(
                prepare_results(frames["passed"]).head(10),
                width="stretch",
                hide_index=True,
            )
        elif frames["impending"].empty:
            st.caption("No stocks have qualified in the processed batch yet.")
        if not frames["impending"].empty:
            st.subheader("Impending Golden Cross stocks so far")
            st.dataframe(
                prepare_results(frames["impending"], impending=True).head(10),
                width="stretch",
                hide_index=True,
            )
    with placeholders["insights"].container():
        render_scan_insights(frames["passed"], frames["failed"])


def render_live_scan_page() -> None:
    session = current_session()
    scroll_to_top()
    pending = session.get("pending_scan")
    if not pending:
        st.subheader("Live scan")
        st.info("No scan is currently running. Configure and start one from Strategy.")
        if st.button("Go to Strategy"):
            navigate_to("2. Strategy")
        return

    symbols = pending["symbols"]
    settings = pending["settings"]
    source = pending["market_data_source"]
    st.subheader(f"Scanning {len(symbols):,} stocks")
    st.caption("Qualified stocks and locally derived insights update every 25 symbols.")
    progress = st.progress(0)
    metric_columns = st.columns(4)
    placeholders = {
        "progress": progress,
        "processed": metric_columns[0].empty(),
        "qualified": metric_columns[1].empty(),
        "impending": metric_columns[2].empty(),
        "rejected": metric_columns[3].empty(),
        "results": st.empty(),
        "insights": st.empty(),
    }
    data_services = build_data_services(source, PROJECT_ROOT)
    settings = {
        **settings,
        "market_data_source": source,
        "market_data_snapshot": data_services.metadata,
        "stock_market": "India — NSE",
        "stock_count": len(symbols),
    }
    workflow_result = ScanWorkflow(data_services).execute(
        RunScanCommand.create(symbols, build_scan_config(settings)),
        result_callback=lambda current, total, run: _live_update(
            current, total, run, placeholders
        ),
    )
    frames = workflow_result.run.as_dataframes()
    session["scan_results"] = frames["passed"]
    session["scan_impending_results"] = frames["impending"]
    session["scan_failed_results"] = frames["failed"]
    session["scan_time"] = datetime.now()
    session["scan_settings"] = settings
    session["scan_metrics"] = workflow_result.run.metrics
    session.pop("pending_scan", None)
    navigate_to("4. Results")


__all__ = ["render_live_scan_page"]
