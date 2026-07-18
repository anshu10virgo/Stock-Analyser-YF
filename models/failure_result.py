from dataclasses import dataclass


@dataclass
class FailureResult:

    symbol: str

    stage: str

    reason: str