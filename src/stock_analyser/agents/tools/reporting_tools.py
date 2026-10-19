"""Reporting-tool boundary reserved for future confirmed side effects."""

from stock_analyser.agents.tool_registry import ToolRegistry


def register_reporting_tools(_registry: ToolRegistry) -> None:
    """Register no tools until report delivery has an explicit agent approval UX."""


__all__ = ["register_reporting_tools"]
