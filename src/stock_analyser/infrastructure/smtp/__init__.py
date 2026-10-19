"""SMTP infrastructure adapters."""

from .mailer import ConfiguredSmtpMailer, MailConfiguration, SmtpMailer

__all__ = ["ConfiguredSmtpMailer", "MailConfiguration", "SmtpMailer"]
