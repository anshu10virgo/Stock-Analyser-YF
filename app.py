"""Thin Streamlit Cloud entrypoint for the packaged application."""

from importlib import reload

from stock_analyser.presentation.streamlit import app as packaged_app


# Streamlit reruns this bootstrap in the same interpreter. Reloading the
# presentation module keeps test patches and per-run imports isolated exactly
# as they were when the complete application lived in this file.
reload(packaged_app)
packaged_app.run()
