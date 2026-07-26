"""Typed configuration for opt-in fundamental filters."""

from __future__ import annotations

from dataclasses import asdict, dataclass


RELATIVE_INDUSTRY_PE = "relative_industry_pe"
HISTORICAL_STOCK_PE = "historical_stock_pe"
PEG_RATIO = "peg_ratio"
PROFIT_GROWTH = "profit_growth"
EPS_GROWTH = "eps_growth"
SALES_GROWTH = "sales_growth"
RETURN_ON_EQUITY = "return_on_equity"
DEBT_TO_EQUITY = "debt_to_equity"
MARKET_CAP = "market_cap"

SUPPORTED_OPTIONAL_FILTERS = (
    RELATIVE_INDUSTRY_PE,
    HISTORICAL_STOCK_PE,
    PEG_RATIO,
    PROFIT_GROWTH,
    EPS_GROWTH,
    SALES_GROWTH,
    RETURN_ON_EQUITY,
    DEBT_TO_EQUITY,
    MARKET_CAP,
)

SCREENER_OPTIONAL_FILTERS = frozenset(
    {
        HISTORICAL_STOCK_PE,
        PEG_RATIO,
        PROFIT_GROWTH,
        EPS_GROWTH,
        SALES_GROWTH,
        RETURN_ON_EQUITY,
        DEBT_TO_EQUITY,
    }
)

MARKET_CAP_BUCKETS = ("large", "mid", "small", "micro")


@dataclass(frozen=True)
class OptionalFilterConfig:
    """One selected fundamental filter and its user-controlled values."""

    key: str
    threshold: float | None = None
    market_cap_buckets: tuple[str, ...] = ()
    custom_min_crore: float | None = None
    custom_max_crore: float | None = None

    @classmethod
    def from_dict(cls, values: dict) -> "OptionalFilterConfig":
        """Build a stable immutable configuration from Streamlit state."""
        return cls(
            key=values["key"],
            threshold=values.get("threshold"),
            market_cap_buckets=tuple(values.get("market_cap_buckets", ())),
            custom_min_crore=values.get("custom_min_crore"),
            custom_max_crore=values.get("custom_max_crore"),
        )

    def as_dict(self) -> dict:
        """Return a session-state-friendly representation."""
        values = asdict(self)
        values["market_cap_buckets"] = list(self.market_cap_buckets)
        return values

    def validate(self) -> None:
        """Reject unsupported or internally inconsistent filter settings."""
        if self.key not in SUPPORTED_OPTIONAL_FILTERS:
            raise ValueError(f"Unsupported optional filter: {self.key}")

        if self.key == PEG_RATIO and (
            self.threshold is None or not 0 <= self.threshold <= 2
        ):
            raise ValueError("PEG threshold must be between 0 and 2")
        if self.key == DEBT_TO_EQUITY and (
            self.threshold is None or not 0 <= self.threshold <= 2
        ):
            raise ValueError("Debt-to-equity threshold must be between 0 and 2")
        if self.key in {
            PROFIT_GROWTH,
            EPS_GROWTH,
            SALES_GROWTH,
            RETURN_ON_EQUITY,
        } and (
            self.threshold is None or not 0 <= self.threshold <= 50
        ):
            raise ValueError(
                f"{self.key} threshold must be between 0 and 50"
            )

        unknown_buckets = set(self.market_cap_buckets) - set(MARKET_CAP_BUCKETS)
        if unknown_buckets:
            raise ValueError(
                f"Unsupported market-cap buckets: {sorted(unknown_buckets)}"
            )
        if self.custom_min_crore is not None and self.custom_min_crore < 0:
            raise ValueError("Custom market-cap minimum cannot be negative")
        if self.custom_max_crore is not None and self.custom_max_crore < 0:
            raise ValueError("Custom market-cap maximum cannot be negative")
        if (
            self.custom_min_crore is not None
            and self.custom_max_crore is not None
            and self.custom_min_crore > self.custom_max_crore
        ):
            raise ValueError(
                "Custom market-cap minimum cannot exceed its maximum"
            )
        if (
            self.key == MARKET_CAP
            and not self.market_cap_buckets
            and self.custom_min_crore is None
            and self.custom_max_crore is None
        ):
            raise ValueError(
                "Market-cap filter requires a bucket or custom boundary"
            )
