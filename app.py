"""Thin Streamlit Cloud entrypoint for the packaged application."""

from importlib import reload
from pathlib import Path
import sys


SOURCE_ROOT = Path(__file__).resolve().parent / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from stock_analyser.presentation.streamlit import app as packaged_app


# Streamlit reruns this bootstrap in the same interpreter. Reloading the
# presentation module keeps test patches and per-run imports isolated exactly
# as they were when the complete application lived in this file.
reload(packaged_app)
packaged_app.run()
