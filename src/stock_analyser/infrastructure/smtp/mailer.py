"""Authenticated SMTP implementation of the application mailer port."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


@dataclass(frozen=True)
class MailConfiguration:
    """Credentials and transport details supplied by deployment secrets."""

    username: str
    password: str
    host: str = SMTP_HOST
    port: int = SMTP_PORT
    timeout_seconds: int = 30


@dataclass(frozen=True)
class SmtpMailer:
    """Send prepared messages through one authenticated SMTP session."""

    configuration: MailConfiguration

    def send(self, messages: list[EmailMessage]) -> None:
        with smtplib.SMTP_SSL(
            self.configuration.host,
            self.configuration.port,
            timeout=self.configuration.timeout_seconds,
        ) as smtp:
            smtp.login(
                self.configuration.username,
                self.configuration.password,
            )
            for message in messages:
                smtp.send_message(message)


# Retain the established composition name while exposing the provider-specific
# adapter name for new infrastructure code.
ConfiguredSmtpMailer = SmtpMailer


__all__ = [
    "ConfiguredSmtpMailer",
    "MailConfiguration",
    "SMTP_HOST",
    "SMTP_PORT",
    "SmtpMailer",
]
