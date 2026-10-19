"""Outbound report-delivery contract."""

from __future__ import annotations

from email.message import EmailMessage
from typing import Protocol, runtime_checkable


@runtime_checkable
class MailerPort(Protocol):
    def send(self, messages: list[EmailMessage]) -> None: ...
