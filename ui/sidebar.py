"""Compatibility alias for packaged strategy controls."""

import sys
from stock_analyser.presentation.streamlit.components import strategy_configuration as _implementation

sys.modules[__name__] = _implementation
