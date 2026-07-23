"""Send a GitHub Actions market-data refresh failure notification."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
DEFAULT_RECIPIENT = "anshu10virgo@gmail.com"


def build_message(environment: dict[str, str]) -> EmailMessage:
    """Build a concise alert containing enough context to inspect the run."""
    repository = environment.get("GITHUB_REPOSITORY", "Stock-Analyser-YF")
    workflow = environment.get("GITHUB_WORKFLOW", "Refresh committed market data")
    run_id = environment.get("GITHUB_RUN_ID", "unknown")
    server_url = environment.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server_url}/{repository}/actions/runs/{run_id}"
    recipient = environment.get("REFRESH_ALERT_RECIPIENT", DEFAULT_RECIPIENT)
    sender = environment["REFRESH_SMTP_USERNAME"]

    message = EmailMessage()
    message["Subject"] = f"Stock Analyser market-data refresh failed ({run_id})"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "The scheduled Stock Analyser market-data refresh failed.\n\n"
        f"Repository: {repository}\n"
        f"Workflow: {workflow}\n"
        f"Branch/ref: {environment.get('GITHUB_REF_NAME', 'unknown')}\n"
        f"Commit: {environment.get('GITHUB_SHA', 'unknown')}\n"
        f"Run: {run_url}\n\n"
        "Open the run link to review the failed step and logs."
    )
    return message


def send_failure_email(environment: dict[str, str] | None = None) -> bool:
    """Send the alert, or report missing secrets without exposing credentials."""
    if environment is None:
        environment = dict(os.environ)
    username = environment.get("REFRESH_SMTP_USERNAME")
    password = environment.get("REFRESH_SMTP_APP_PASSWORD")
    if not username or not password:
        print(
            "::warning::Refresh email was not sent because "
            "REFRESH_SMTP_USERNAME or REFRESH_SMTP_APP_PASSWORD is not configured."
        )
        return False

    message = build_message(environment)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)
    print(f"Refresh failure email sent to {message['To']}.")
    return True


if __name__ == "__main__":
    send_failure_email()
