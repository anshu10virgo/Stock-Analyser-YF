"""Typed data exchanged by Ticksy and its model providers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantMessage:
    """One session-only user or assistant chat message."""

    role: str
    content: str


@dataclass(frozen=True)
class AssistantSettings:
    """Configuration for one selected hosted assistant provider."""

    provider: str
    model: str
    api_key: str | None = None


@dataclass(frozen=True)
class AssistantRequest:
    """The bounded local context supplied for one model response."""

    messages: tuple[AssistantMessage, ...]
    local_context: str
