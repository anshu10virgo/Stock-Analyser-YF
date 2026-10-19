"""Typed contracts for safe agent tool discovery and execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any
from uuid import uuid4


class ApprovalLevel(str, Enum):
    NONE = "none"
    USER_CONFIRMATION = "user_confirmation"
    ADMIN_CONFIRMATION = "admin_confirmation"


class ToolEffect(str, Enum):
    READ_ONLY = "read_only"
    SESSION_MUTATION = "session_mutation"
    EXPENSIVE_COMPUTE = "expensive_compute"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    PRODUCTION_OPERATION = "production_operation"


class ToolStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    APPROVAL_REQUIRED = "approval_required"


@dataclass(frozen=True)
class ArgumentSpec:
    """One validated input accepted by an agent tool."""

    value_type: type | tuple[type, ...]
    required: bool = True
    description: str = ""
    default: Any = None


@dataclass(frozen=True)
class ToolDefinition:
    """Discoverable description and permission policy for one tool."""

    name: str
    description: str
    effect: ToolEffect
    approval: ApprovalLevel
    arguments: dict[str, ArgumentSpec] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class ToolCall:
    """One model- or application-requested tool invocation."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class ToolResult:
    """Structured tool outcome suitable for deterministic rendering."""

    call_id: str
    tool_name: str
    status: ToolStatus
    data: Any = None
    error: str | None = None
    approval: ApprovalLevel = ApprovalLevel.NONE
    audit_id: str | None = None


class ToolValidationError(ValueError):
    """Raised when a tool call does not match its declared input contract."""


__all__ = [
    "ApprovalLevel",
    "ArgumentSpec",
    "ToolCall",
    "ToolDefinition",
    "ToolEffect",
    "ToolResult",
    "ToolStatus",
    "ToolValidationError",
]
