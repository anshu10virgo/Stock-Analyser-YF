"""Compatibility alias for the packaged Introduction page."""

import sys
from stock_analyser.presentation.streamlit.pages import introduction as _implementation

sys.modules[__name__] = _implementation
