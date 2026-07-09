"""API request/response models."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    email: str = Field(..., min_length=5, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=8, max_length=200)


class LoanInput(BaseModel):
    ltv: Optional[float] = Field(None, gt=0, lt=1, description="Loan-to-value; alternative to amount")
    amount: Optional[float] = Field(None, gt=0)
    annual_rate: float = Field(..., ge=0, le=1)
    term_years: float = Field(..., gt=0, le=50)
    interest_only_years: float = Field(0.0, ge=0)


class DealInput(BaseModel):
    name: str = "Untitled deal"
    jurisdiction: str = "tz"
    currency: str = "TZS"
    use: Literal["residential", "commercial"] = "residential"
    tenure: Literal["granted", "customary", "tic_derivative", "other"] = "granted"
    buyer_resident: bool = True
    is_crowdfunded: bool = False

    purchase_price: float = Field(..., gt=0)
    gross_rent_annual: float = Field(..., gt=0)
    vacancy_rate: float = Field(0.05, ge=0, lt=1)
    operating_expenses_annual: float = Field(0.0, ge=0)
    rent_growth: float = Field(0.05, ge=-0.5, le=1)
    expense_growth: float = Field(0.05, ge=-0.5, le=1)
    capex_reserve_rate: float = Field(0.0, ge=0, lt=1)
    hold_years: int = Field(5, ge=1, le=30)
    exit_cap_rate: float = Field(0.08, gt=0, lt=1)
    selling_costs_rate: float = Field(0.03, ge=0, lt=1)
    discount_rate: float = Field(0.12, gt=-1, lt=1)
    loan: Optional[LoanInput] = None


class ComparableInput(BaseModel):
    name: str
    sale_price: float = Field(..., gt=0)
    adjustments: dict[str, float] = Field(default_factory=dict,
                                          description="Signed fractions of sale price, e.g. {'location': 0.05}")
    weight: float = Field(1.0, ge=0)


class ValuationRequest(BaseModel):
    stabilized_noi: Optional[float] = Field(None, gt=0)
    market_cap_rate: Optional[float] = Field(None, gt=0, lt=1)
    deal: Optional[DealInput] = None
    comparables: list[ComparableInput] = Field(default_factory=list)
    approach_weights: Optional[dict[str, float]] = None


class CompIn(BaseModel):
    kind: Literal["sale", "rent"]
    use: Literal["residential", "commercial", "land"]
    region: str = Field(..., min_length=2)
    district: str = Field(..., min_length=2)
    price: float = Field(..., gt=0, description="Sale price, or ANNUAL rent for kind=rent")
    currency: str = "TZS"
    area_sqm: Optional[float] = Field(None, gt=0)
    observed_date: str = Field(..., pattern=r"^\d{4}-\d{2}(-\d{2})?$",
                               description="YYYY-MM or YYYY-MM-DD")
    source: str = Field(..., min_length=3, description="Where this observation comes from")
    contributor: str = "anonymous"
    notes: str = ""


class IndicateRequest(BaseModel):
    area_sqm: float = Field(..., gt=0)
    kind: Literal["sale", "rent"] = "sale"
    use: Optional[Literal["residential", "commercial", "land"]] = None
    region: Optional[str] = None
    district: Optional[str] = None
    since: Optional[str] = None


class IngestJsonRequest(BaseModel):
    source: str = Field(..., min_length=2, description="Feed name, e.g. 'kupatana' or 'partner-x'")
    records: list[dict] = Field(..., min_length=1)
    mapping: Optional[dict[str, str]] = Field(None, description="canonical_field -> input_key")
    dry_run: bool = True


class AvmRequest(BaseModel):
    area_sqm: float = Field(..., gt=0)
    kind: Literal["sale", "rent"] = "sale"
    use: Optional[Literal["residential", "commercial", "land"]] = None
    region: Optional[str] = None
    district: Optional[str] = None
    since: Optional[str] = None


class MonteCarloRequest(BaseModel):
    deal: DealInput
    n: int = Field(1000, ge=100, le=5000)
    seed: Optional[int] = None


class YearRowOut(BaseModel):
    year: int
    gross_potential_income: float
    vacancy_loss: float
    effective_gross_income: float
    operating_expenses: float
    noi: float
    capex_reserve: float
    cash_flow_before_debt: float
    debt_service: float
    cash_flow_after_debt: float


class SaleOut(BaseModel):
    year: int
    gross_sale_price: float
    selling_costs: float
    loan_payoff: float
    net_sale_proceeds_unlevered: float
    net_sale_proceeds_levered: float


class AnalysisResult(BaseModel):
    deal: DealInput
    metrics: dict
    years: list[YearRowOut]
    sale: SaleOut
    acquisition_costs: dict
    disposal_taxes: dict
    rental_withholding: dict
    compliance_flags: list[dict]
    procedure_steps: list[dict]
    rulepack: dict
    disclaimer: str
