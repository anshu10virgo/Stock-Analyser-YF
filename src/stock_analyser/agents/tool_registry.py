"""Discoverable, policy-checked registry for deterministic agent tools."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from stock_analyser.agents.approvals import approval_granted
from stock_analyser.agents.audit_log import InMemoryAuditLog
from stock_analyser.agents.contracts import (
    ApprovalLevel,
    ToolCall,
    ToolDefinition,
    ToolResult,
    ToolStatus,
    ToolValidationError,
)
from stock_analyser.agents.execution_context import ExecutionContext
from stock_analyser.agents.policies import validate_tool_policy


ToolHandler = Callable[[ExecutionContext, dict[str, Any]], Any]


@dataclass(frozen=True)
class RegisteredTool:
    definition: ToolDefinition
    handler: ToolHandler


class ToolRegistry:
    """Allow-list and execute typed tools through one controlled boundary."""

    def __init__(self, audit_log: InMemoryAuditLog | None = None) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self.audit_log = audit_log or InMemoryAuditLog()

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        validate_tool_policy(definition.effect, definition.approval)
        if definition.name in self._tools:
            raise ValueError(f"Agent tool is already registered: {definition.name}")
        self._tools[definition.name] = RegisteredTool(definition, handler)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(tool.definition for tool in self._tools.values())

    def execute(
        self,
        call: ToolCall,
        context: ExecutionContext,
        *,
        approved: bool = False,
        admin_approved: bool = False,
    ) -> ToolResult:
        started_at = datetime.now(timezone.utc)
        registered = self._tools.get(call.name)
        if registered is None:
            return self._error(
                call,
                ApprovalLevel.NONE,
                context,
                started_at,
                "Unknown agent tool",
            )

        definition = registered.definition
        try:
            arguments = self._validate_arguments(definition, call.arguments)
        except ToolValidationError as error:
            return self._error(
                call,
                definition.approval,
                context,
                started_at,
                str(error),
            )

        authorized = approval_granted(
            definition.approval,
            user_approved=approved,
            admin_approved=admin_approved,
        )
        if not authorized:
            event = self.audit_log.record(
                call,
                definition.approval,
                False,
                ToolStatus.APPROVAL_REQUIRED,
                context.snapshot_identity,
                started_at,
            )
            return ToolResult(
                call.call_id,
                call.name,
                ToolStatus.APPROVAL_REQUIRED,
                approval=definition.approval,
                audit_id=event.event_id,
            )

        try:
            data = registered.handler(context, arguments)
        except Exception as error:
            return self._error(
                call,
                definition.approval,
                context,
                started_at,
                f"{type(error).__name__}: {error}",
                approved=True,
            )
        event = self.audit_log.record(
            call,
            definition.approval,
            True,
            ToolStatus.SUCCESS,
            context.snapshot_identity,
            started_at,
        )
        return ToolResult(
            call.call_id,
            call.name,
            ToolStatus.SUCCESS,
            data=data,
            approval=definition.approval,
            audit_id=event.event_id,
        )

    @staticmethod
    def _validate_arguments(
        definition: ToolDefinition,
        supplied: dict[str, Any],
    ) -> dict[str, Any]:
        unknown = set(supplied) - set(definition.arguments)
        if unknown:
            raise ToolValidationError(
                f"Unexpected argument(s) for {definition.name}: "
                f"{', '.join(sorted(unknown))}"
            )
        validated = {}
        for name, spec in definition.arguments.items():
            if name not in supplied:
                if spec.required:
                    raise ToolValidationError(
                        f"Missing required argument for {definition.name}: {name}"
                    )
                validated[name] = spec.default
                continue
            value = supplied[name]
            if not isinstance(value, spec.value_type):
                expected = (
                    ", ".join(
                        value_type.__name__ for value_type in spec.value_type
                    )
                    if isinstance(spec.value_type, tuple)
                    else spec.value_type.__name__
                )
                raise ToolValidationError(
                    f"Argument {name} for {definition.name} must be {expected}"
                )
            validated[name] = value
        return validated

    def _error(
        self,
        call: ToolCall,
        approval: ApprovalLevel,
        context: ExecutionContext,
        started_at: datetime,
        error: str,
        approved: bool = False,
    ) -> ToolResult:
        event = self.audit_log.record(
            call,
            approval,
            approved,
            ToolStatus.ERROR,
            context.snapshot_identity,
            started_at,
            error,
        )
        return ToolResult(
            call.call_id,
            call.name,
            ToolStatus.ERROR,
            error=error,
            approval=approval,
            audit_id=event.event_id,
        )


__all__ = ["RegisteredTool", "ToolHandler", "ToolRegistry"]
