"""Hosted-model contract kept independent from concrete AI providers."""

from __future__ import annotations

from typing import Any, Protocol

from models.assistant import AssistantRequest


class ModelProviderPort(Protocol):
    def respond(self, request: AssistantRequest) -> str: ...

    def select_tools(
        self, request: AssistantRequest, tools: tuple[Any, ...]
    ) -> tuple[Any, ...]: ...
