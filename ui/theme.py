"""Compatibility alias for the packaged Streamlit theme."""

import sys
from stock_analyser.presentation.streamlit.components import theme as _implementation

sys.modules[__name__] = _implementation
