"""Grounded orchestration for Ticksy's bounded local tool calls."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from models.assistant import AssistantMessage, AssistantRequest
from stock_analyser.agents.contracts import ToolCall, ToolResult, ToolStatus
from stock_analyser.agents.execution_context import (
    ExecutionContext,
    build_local_context,
)
from stock_analyser.agents.tool_registry import ToolRegistry
from stock_analyser.agents.tools import build_local_tool_registry
from stock_analyser.application.context import ApplicationContext
from stock_analyser.application.ports.model_provider import ModelProviderPort


ContextSource = Mapping[str, Any] | ApplicationContext | ExecutionContext


@dataclass(frozen=True)
class AssistantAnswer:
    """One grounded provider answer and the local sources used for it."""

    text: str
    tools: tuple[str, ...] = ()
    scan_time: str | None = None
    snapshot_identity: str | None = None

    def render(self) -> str:
        sources = ["bounded local application data"]
        if self.scan_time:
            sources.append(f"scan {self.scan_time}")
        if self.snapshot_identity:
            sources.append(f"snapshot {self.snapshot_identity}")
        if self.tools:
            names = ", ".join(name.replace("_", " ") for name in self.tools)
            sources.append(f"tools: {names}")
        return f"{self.text}\n\n_Data used: {' · '.join(sources)}._"


class AssistantRuntime:
    """Build bounded context and execute only allow-listed deterministic tools."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        max_tool_calls: int = 3,
    ) -> None:
        self.registry = registry or build_local_tool_registry()
        self.max_tool_calls = max_tool_calls

    @staticmethod
    def context(source: ContextSource) -> ExecutionContext:
        if isinstance(source, ExecutionContext):
            return source
        if isinstance(source, ApplicationContext):
            return ExecutionContext.from_application_context(source)
        return ExecutionContext.from_application_state(source)

    def execute(
        self,
        source: ContextSource,
        call: ToolCall,
        *,
        approved: bool = False,
        admin_approved: bool = False,
    ) -> ToolResult:
        return self.registry.execute(
            call,
            self.context(source),
            approved=approved,
            admin_approved=admin_approved,
        )

    def answer(
        self,
        provider: ModelProviderPort,
        source: ContextSource,
        messages: tuple[AssistantMessage, ...],
        stock_query: str = "",
    ) -> AssistantAnswer:
        """Let the provider select bounded tools, then ground its final answer."""
        context = self.context(source)
        local_context = build_local_context(context, stock_query)
        request = AssistantRequest(messages, local_context)
        calls = provider.select_tools(request, self.registry.definitions())
        selected = calls[: self.max_tool_calls]
        results = tuple(self.registry.execute(call, context) for call in selected)
        if results and all(_result_is_unavailable(result) for result in results):
            return AssistantAnswer(
                "That information is not available in the current local scan or Backtester results.",
                tuple(result.tool_name for result in results),
                _optional_text(context.get("scan_time")),
                context.snapshot_identity,
            )
        if results:
            grounded_context = _grounded_context(local_context, results)
            request = AssistantRequest(messages, grounded_context)
        response = provider.respond(request)
        return AssistantAnswer(
            response,
            tuple(result.tool_name for result in results),
            _optional_text(context.get("scan_time")),
            context.snapshot_identity,
        )


def _grounded_context(local_context: str, results: tuple[ToolResult, ...]) -> str:
    return json.dumps(
        {
            "application_context": json.loads(local_context),
            "tool_results": [
                {
                    **asdict(result),
                    "status": result.status.value,
                    "approval": result.approval.value,
                }
                for result in results
            ],
            "instruction": (
                "Use only successful tool results. If a result is unavailable or "
                "failed, say the information is not available in the current scan."
            ),
        },
        default=str,
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _result_is_unavailable(result: ToolResult) -> bool:
    if result.status != ToolStatus.SUCCESS:
        return True
    if isinstance(result.data, dict):
        return result.data.get("available") is False
    if isinstance(result.data, (list, tuple)):
        return not result.data
    return result.data is None


__all__ = ["AssistantAnswer", "AssistantRuntime", "ContextSource"]
