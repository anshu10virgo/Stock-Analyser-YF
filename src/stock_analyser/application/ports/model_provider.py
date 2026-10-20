"""Hosted-model contract kept independent from concrete AI providers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from stock_analyser.agents.models import AssistantRequest
from stock_analyser.agents.contracts import ToolCall, ToolDefinition


class ModelProviderError(RuntimeError):
    """Base error exposed by hosted-model adapters."""


class ModelProviderTransportError(ModelProviderError):
    """A provider request failed before a usable response was returned."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ModelProviderResponseError(ModelProviderError):
    """A provider returned an empty or malformed response."""


@runtime_checkable
class ModelProviderPort(Protocol):
    def respond(self, request: AssistantRequest) -> str: ...

    def select_tools(
        self,
        request: AssistantRequest,
        tools: tuple[ToolDefinition, ...],
    ) -> tuple[ToolCall, ...]: ...
