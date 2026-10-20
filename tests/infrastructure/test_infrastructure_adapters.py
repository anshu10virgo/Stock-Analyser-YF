"""Contract and compatibility tests for external-system adapters."""

from __future__ import annotations

import unittest
from email.message import EmailMessage
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from stock_analyser.application.commands.send_report import SendReport, SendReportCommand
from stock_analyser.application.ports import (
    FundamentalsPort,
    IndustryValuationPort,
    MailerPort,
    MarketDataPort,
    ScreenerFundamentalsPort,
    StoragePort,
)
from stock_analyser.infrastructure.r2.repository import (
    RepositoryHistoryProvider,
    RepositoryScreenerProvider,
)
from stock_analyser.infrastructure.r2.storage import LocalSnapshotStorage
from stock_analyser.infrastructure.smtp.mailer import MailConfiguration, SmtpMailer
from stock_analyser.infrastructure.yahoo.fundamentals import YahooFundamentalsProvider
from stock_analyser.infrastructure.yahoo.industry_valuation import (
    YahooIndustryValuationService,
)
from stock_analyser.infrastructure.yahoo.providers import YahooFinanceHistoryProvider


class InfrastructureAdapterTests(unittest.TestCase):
    def test_concrete_adapters_satisfy_application_ports(self):
        with TemporaryDirectory() as directory:
            storage = LocalSnapshotStorage(Path(directory))

            self.assertIsInstance(YahooFinanceHistoryProvider(), MarketDataPort)
            self.assertIsInstance(RepositoryHistoryProvider(Path(directory)), MarketDataPort)
            self.assertIsInstance(YahooFundamentalsProvider(), FundamentalsPort)
            self.assertIsInstance(
                YahooIndustryValuationService(), IndustryValuationPort
            )
            self.assertIsInstance(
                RepositoryScreenerProvider(Path(directory)),
                ScreenerFundamentalsPort,
            )
            self.assertIsInstance(storage, StoragePort)
            self.assertIsInstance(
                SmtpMailer(MailConfiguration("sender@example.com", "secret")),
                MailerPort,
            )

    @patch("stock_analyser.infrastructure.smtp.mailer.smtplib.SMTP_SSL")
    def test_report_command_delivers_through_smtp_port(self, smtp_ssl):
        message = EmailMessage()
        message["Subject"] = "Infrastructure adapter test"
        message["From"] = "sender@example.com"
        message["To"] = "recipient@example.com"
        message.set_content("Test")
        command = SendReportCommand((message,))
        mailer = SmtpMailer(MailConfiguration("sender@example.com", "secret"))

        delivered = SendReport(mailer).execute(command)

        self.assertEqual(delivered, 1)
        smtp = smtp_ssl.return_value.__enter__.return_value
        smtp.login.assert_called_once_with("sender@example.com", "secret")
        smtp.send_message.assert_called_once_with(message)


if __name__ == "__main__":
    unittest.main()
