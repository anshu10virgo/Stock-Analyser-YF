"""Compatibility alias for packaged scan-insight components."""

import sys
from stock_analyser.presentation.streamlit.components import scan_insights as _implementation

sys.modules[__name__] = _implementation
