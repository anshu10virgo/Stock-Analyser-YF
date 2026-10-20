"""Compatibility alias for packaged result components."""

import sys
from stock_analyser.presentation.streamlit.components import results as _implementation

sys.modules[__name__] = _implementation
