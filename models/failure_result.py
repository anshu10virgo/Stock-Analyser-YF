"""Structured rejection and processing-failure records."""

from dataclasses import asdict, dataclass


@dataclass
class FailureResult:

    symbol: str

    stage: str

    reason: str

    check_type: str = "mandatory"

    def as_dict(self) -> dict:
        return asdict(self)
