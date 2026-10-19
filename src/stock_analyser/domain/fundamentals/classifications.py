"""Provider-independent company classification rules."""

from collections.abc import Mapping


FINANCIAL_COMPANY_TERMS = (
    "bank",
    "financial",
    "insurance",
    "credit service",
    "capital market",
    "asset management",
    "mortgage",
)


def is_financial_company(fundamentals: Mapping) -> bool:
    """Return whether sector or industry describes a financial company."""
    classification = " ".join(
        str(fundamentals.get(field) or "").lower()
        for field in ("sector", "industry")
    )
    return any(term in classification for term in FINANCIAL_COMPANY_TERMS)


__all__ = ["FINANCIAL_COMPANY_TERMS", "is_financial_company"]
