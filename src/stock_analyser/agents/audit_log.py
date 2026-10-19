"""Sanitized, session-local audit records for agent tool execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from stock_analyser.agents.contracts import ApprovalLevel, ToolCall, ToolStatus


SENSITIVE_ARGUMENT_TERMS = (
    "password",
    "secret",
    "token",
    "api_key",
    "credential",
)


def _sanitized_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return sanitized_arguments(value)
    if isinstance(value, list):
        return [_sanitized_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitized_value(item) for item in value)
    return value


def sanitized_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively remove credential-like values from audit arguments."""
    sanitized = {}
    for key, value in arguments.items():
        sanitized[key] = (
            "[REDACTED]"
            if any(term in key.lower() for term in SENSITIVE_ARGUMENT_TERMS)
            else _sanitized_value(value)
        )
    return sanitized


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    approval: ApprovalLevel
    approved: bool
    status: ToolStatus
    snapshot_identity: str | None
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    error: str | None = None


class InMemoryAuditLog:
    """Thread-safe session audit store; durable storage may replace it later."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = RLock()

    def record(
        self,
        call: ToolCall,
        approval: ApprovalLevel,
        approved: bool,
        status: ToolStatus,
        snapshot_identity: str | None,
        started_at: datetime,
        error: str | None = None,
    ) -> AuditEvent:
        completed_at = datetime.now(timezone.utc)
        event = AuditEvent(
            event_id=str(uuid4()),
            call_id=call.call_id,
            tool_name=call.name,
            arguments=sanitized_arguments(call.arguments),
            approval=approval,
            approved=approved,
            status=status,
            snapshot_identity=snapshot_identity,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=(completed_at - started_at).total_seconds() * 1000,
            error=error,
        )
        with self._lock:
            self._events.append(event)
        return event

    def events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)


__all__ = [
    "AuditEvent",
    "InMemoryAuditLog",
    "SENSITIVE_ARGUMENT_TERMS",
    "sanitized_arguments",
]
