"""Compatibility alias for the packaged Ticksy component."""

import sys
from stock_analyser.presentation.streamlit.components import ticksy as _implementation

sys.modules[__name__] = _implementation
