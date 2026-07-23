"""Tests for scheduled-refresh failure email construction and delivery."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.send_refresh_failure_email import build_message, send_failure_email


class RefreshFailureEmailTests(unittest.TestCase):
    @staticmethod
    def _environment():
        return {
            "REFRESH_SMTP_USERNAME": "sender@example.com",
            "REFRESH_SMTP_APP_PASSWORD": "secret",
            "REFRESH_ALERT_RECIPIENT": "anshu10virgo@gmail.com",
            "GITHUB_REPOSITORY": "anshu10virgo/Stock-Analyser-YF",
            "GITHUB_WORKFLOW": "Refresh committed market data",
            "GITHUB_RUN_ID": "12345",
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REF_NAME": "main",
            "GITHUB_SHA": "abc123",
            "REFRESH_ALERT_IS_TEST": "true",
            "REFRESH_ALERT_REFERENCE_RUN_URL": "https://github.com/example/actions/runs/999",
        }

    def test_message_contains_recipient_and_run_link(self):
        message = build_message(self._environment())

        self.assertEqual(message["To"], "anshu10virgo@gmail.com")
        self.assertIn(
            "https://github.com/anshu10virgo/Stock-Analyser-YF/actions/runs/12345",
            message.get_content(),
        )
        self.assertIn("refresh alert test", message["Subject"])
        self.assertIn(
            "Referenced failed run: https://github.com/example/actions/runs/999",
            message.get_content(),
        )

    @patch("scripts.send_refresh_failure_email.smtplib.SMTP_SSL")
    def test_delivery_uses_authenticated_gmail_smtp(self, smtp_ssl):
        delivered = send_failure_email(self._environment())

        self.assertTrue(delivered)
        smtp_ssl.assert_called_once_with("smtp.gmail.com", 465, timeout=30)
        smtp = smtp_ssl.return_value.__enter__.return_value
        smtp.login.assert_called_once_with("sender@example.com", "secret")
        smtp.send_message.assert_called_once()

    def test_missing_secrets_skip_delivery_without_crashing(self):
        self.assertFalse(send_failure_email({}))


if __name__ == "__main__":
    unittest.main()
