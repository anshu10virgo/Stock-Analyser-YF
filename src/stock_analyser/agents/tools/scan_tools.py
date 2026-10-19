"""Read-only tools over completed local scan results."""

from stock_analyser.agents.contracts import (
    ApprovalLevel,
    ArgumentSpec,
    ToolDefinition,
    ToolEffect,
)
from stock_analyser.agents.execution_context import ExecutionContext
from stock_analyser.agents.tool_registry import ToolRegistry
from stock_analyser.application.queries import (
    explain_failure_summary,
    get_market_condition,
    get_scan_summary,
    get_stock_status,
)


def _scan_summary(context: ExecutionContext, _arguments: dict):
    return get_scan_summary(context.as_mapping())


def _stock_status(context: ExecutionContext, arguments: dict):
    return get_stock_status(context.as_mapping(), arguments["symbol"])


def _market_condition(context: ExecutionContext, _arguments: dict):
    return get_market_condition(context.as_mapping())


def _rejection_summary(context: ExecutionContext, arguments: dict):
    limit = max(1, min(10, arguments.get("limit", 5)))
    return explain_failure_summary(context.as_mapping(), limit)


def register_scan_tools(registry: ToolRegistry) -> None:
    """Register scan tools in their established discovery order."""
    registry.register(
        ToolDefinition(
            "get_scan_summary",
            "Return counts and timestamp from the completed local scan.",
            ToolEffect.READ_ONLY,
            ApprovalLevel.NONE,
        ),
        _scan_summary,
    )
    registry.register(
        ToolDefinition(
            "get_stock_status",
            "Return the stored Post, Impending, or failed result for one stock.",
            ToolEffect.READ_ONLY,
            ApprovalLevel.NONE,
            {
                "symbol": ArgumentSpec(
                    str,
                    description="NSE Yahoo symbol or company query",
                )
            },
        ),
        _stock_status,
    )
    registry.register(
        ToolDefinition(
            "get_market_condition",
            "Summarise only the current completed local scan.",
            ToolEffect.READ_ONLY,
            ApprovalLevel.NONE,
        ),
        _market_condition,
    )


def register_rejection_tool(registry: ToolRegistry) -> None:
    """Register rejection analysis after the other established tools."""
    registry.register(
        ToolDefinition(
            "get_rejection_summary",
            "Return readable counts for the most common local scan rejections.",
            ToolEffect.READ_ONLY,
            ApprovalLevel.NONE,
            {
                "limit": ArgumentSpec(
                    int,
                    required=False,
                    description="Maximum number of rejection reasons, from 1 to 10",
                    default=5,
                )
            },
        ),
        _rejection_summary,
    )


__all__ = ["register_rejection_tool", "register_scan_tools"]
