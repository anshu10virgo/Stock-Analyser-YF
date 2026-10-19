"""Focused deterministic tools exposed through Ticksy's registry."""

from stock_analyser.agents.tool_registry import ToolRegistry
from stock_analyser.agents.tools.backtest_tools import register_backtest_tools
from stock_analyser.agents.tools.data_health_tools import register_data_health_tools
from stock_analyser.agents.tools.explanation_tools import register_explanation_tools
from stock_analyser.agents.tools.reporting_tools import register_reporting_tools
from stock_analyser.agents.tools.scan_tools import (
    register_rejection_tool,
    register_scan_tools,
)


def build_local_tool_registry() -> ToolRegistry:
    """Return the existing allow-list in its stable provider discovery order."""
    registry = ToolRegistry()
    register_scan_tools(registry)
    register_backtest_tools(registry)
    register_explanation_tools(registry)
    register_data_health_tools(registry)
    register_rejection_tool(registry)
    register_reporting_tools(registry)
    return registry


__all__ = ["build_local_tool_registry"]
