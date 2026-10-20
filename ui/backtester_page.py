"""Compatibility alias for the packaged Backtester page."""

import sys
from stock_analyser.presentation.streamlit.pages import backtester as _implementation

sys.modules[__name__] = _implementation
