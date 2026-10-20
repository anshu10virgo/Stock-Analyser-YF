"""Compatibility alias for packaged stock-detail components."""

import sys
from stock_analyser.presentation.streamlit.components import stock_detail as _implementation

sys.modules[__name__] = _implementation
