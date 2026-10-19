"""Compatibility and configuration facade for hosted model adapters.

Provider-specific HTTP payloads and response parsing live under
``stock_analyser.infrastructure``. This module remains the stable composition
path used by the current Streamlit presentation during migration.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from models.assistant import AssistantRequest, AssistantSettings
from stock_analyser.agents.contracts import ToolCall, ToolDefinition
from stock_analyser.agents.prompts import (
    SYSTEM_INSTRUCTION,
    TOOL_SELECTION_INSTRUCTION,
)
from stock_analyser.application.ports.model_provider import ModelProviderPort
from stock_analyser.infrastructure.gemini.provider import GeminiProvider
from stock_analyser.infrastructure.openai.provider import OpenAIProvider


AssistantProvider = ModelProviderPort


class DisabledProvider:
    """Safe provider used when no configured API key is available."""

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def respond(self, request: AssistantRequest) -> str:
        return (
            f"Ticksy is ready for local analysis, but the {self.provider} API key "
            "is not configured. Add it to Streamlit Secrets to enable chat."
        )

    def select_tools(
        self,
        request: AssistantRequest,
        tools: tuple[ToolDefinition, ...],
    ) -> tuple[ToolCall, ...]:
        return ()


def load_assistant_settings(secrets: Mapping | None = None) -> AssistantSettings:
    """Load provider settings without exposing credentials to the interface."""
    configured = secrets or {}
    assistant = configured.get("assistant", {})
    provider = str(
        assistant.get("provider", os.getenv("ASSISTANT_PROVIDER", "gemini"))
    ).lower()
    gemini_model = str(
        assistant.get("gemini_model", os.getenv("GEMINI_MODEL", "gemini-3.7-flash"))
    )
    openai_model = str(
        assistant.get("openai_model", os.getenv("OPENAI_MODEL", "gpt-5.6-terra"))
    )
    api_key_name = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
    api_key = configured.get(api_key_name) or os.getenv(api_key_name)
    model = gemini_model if provider == "gemini" else openai_model
    return AssistantSettings(provider=provider, model=model, api_key=api_key)


def build_provider(settings: AssistantSettings) -> ModelProviderPort:
    """Return the selected adapter or a safe no-key fallback."""
    if not settings.api_key:
        return DisabledProvider(settings.provider)
    if settings.provider == "gemini":
        return GeminiProvider(settings.api_key, settings.model)
    if settings.provider == "openai":
        return OpenAIProvider(settings.api_key, settings.model)
    return DisabledProvider(settings.provider)


__all__ = [
    "AssistantProvider",
    "DisabledProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "SYSTEM_INSTRUCTION",
    "TOOL_SELECTION_INSTRUCTION",
    "build_provider",
    "load_assistant_settings",
]
