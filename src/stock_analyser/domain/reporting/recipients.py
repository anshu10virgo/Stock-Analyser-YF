"""Recipient validation that is independent of SMTP transport."""

import re


EMAIL_PATTERN = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")


def parse_recipients(raw_recipients: str) -> tuple[str, ...]:
    candidates = [value.strip() for value in raw_recipients.split(",") if value.strip()]
    invalid = [value for value in candidates if not EMAIL_PATTERN.fullmatch(value)]
    if invalid:
        raise ValueError("Invalid email address: " + ", ".join(invalid))
    if not candidates:
        raise ValueError("Enter at least one recipient email address")
    return tuple(dict.fromkeys(candidates))


__all__ = ["EMAIL_PATTERN", "parse_recipients"]
