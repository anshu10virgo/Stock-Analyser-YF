"""Provider-independent fundamental models, classifications, and calculations."""

from stock_analyser.domain.fundamentals.calculations import (
    compound_annual_growth_rate,
    debt_to_equity,
    finite_number,
    industry_valuation,
    peg_ratio,
    price_to_earnings,
)
from stock_analyser.domain.fundamentals.classifications import (
    FINANCIAL_COMPANY_TERMS,
    is_financial_company,
)
from stock_analyser.domain.fundamentals.models import (
    EvaluationStatus,
    FilterEvaluation,
    IndustryValuation,
)

__all__ = [
    "EvaluationStatus",
    "FINANCIAL_COMPANY_TERMS",
    "FilterEvaluation",
    "IndustryValuation",
    "compound_annual_growth_rate",
    "debt_to_equity",
    "finite_number",
    "industry_valuation",
    "is_financial_company",
    "peg_ratio",
    "price_to_earnings",
]
