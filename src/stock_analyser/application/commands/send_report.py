"""Deliver already-built report messages through a mailer port."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage

from stock_analyser.application.ports.mailer import MailerPort


@dataclass(frozen=True)
class SendReportCommand:
    messages: tuple[EmailMessage, ...]


class SendReport:
    def __init__(self, mailer: MailerPort) -> None:
        self._mailer = mailer

    def execute(self, command: SendReportCommand) -> int:
        if not command.messages:
            raise ValueError("At least one report message is required")
        self._mailer.send(list(command.messages))
        return len(command.messages)
