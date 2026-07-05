"""Multi-year pro forma builder for income-producing property.

Pure calculation: takes assumptions, returns year-by-year cash flows plus
levered/unlevered return metrics. Jurisdiction taxes and fees are handled
outside this module (app.rulepack) and passed in as costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .tvm import npv, irr
from .loans import annual_debt_service, remaining_balance, payment as loan_payment
from . import metrics as m


@dataclass(frozen=True)
class LoanTerms:
    amount: float
    annual_rate: float
    term_years: float
    interest_only_years: float = 0.0
    periods_per_year: int = 12


@dataclass(frozen=True)
class Assumptions:
    purchase_price: float
    gross_rent_annual: float          # year-1 gross potential rent
    acquisition_costs: float = 0.0    # stamp duty, fees, etc. (from rule pack)
    vacancy_rate: float = 0.05
    operating_expenses_annual: float = 0.0   # year-1 opex
    rent_growth: float = 0.0
    expense_growth: float = 0.0
    capex_reserve_rate: float = 0.0   # share of EGI set aside below NOI
    hold_years: int = 5
    exit_cap_rate: float = 0.08
    selling_costs_rate: float = 0.03
    discount_rate: float = 0.10
    loan: Optional[LoanTerms] = None


@dataclass(frozen=True)
class YearRow:
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


@dataclass(frozen=True)
class SaleSummary:
    year: int
    gross_sale_price: float
    selling_costs: float
    loan_payoff: float
    net_sale_proceeds_unlevered: float   # gross - selling costs
    net_sale_proceeds_levered: float     # gross - selling costs - payoff


@dataclass(frozen=True)
class ProForma:
    assumptions: Assumptions
    years: list[YearRow]
    sale: SaleSummary
    equity_invested: float
    unlevered_cashflows: list[float]     # t=0..hold
    levered_cashflows: list[float]       # t=0..hold
    metrics: dict = field(default_factory=dict)


def _year_row(a: Assumptions, year: int, ds: float) -> YearRow:
    gpi = a.gross_rent_annual * (1.0 + a.rent_growth) ** (year - 1)
    vacancy = gpi * a.vacancy_rate
    egi = gpi - vacancy
    opex = a.operating_expenses_annual * (1.0 + a.expense_growth) ** (year - 1)
    year_noi = m.noi(egi, opex)
    capex = egi * a.capex_reserve_rate
    cfbd = year_noi - capex
    return YearRow(year, gpi, vacancy, egi, opex, year_noi, capex, cfbd, ds, cfbd - ds)


def build_pro_forma(a: Assumptions) -> ProForma:
    if a.hold_years < 1:
        raise ValueError("hold_years must be at least 1")
    if a.exit_cap_rate <= 0:
        raise ValueError("exit_cap_rate must be positive")

    loan = a.loan
    ds = (annual_debt_service(loan.amount, loan.annual_rate, loan.term_years,
                              loan.periods_per_year, loan.interest_only_years)
          if loan else 0.0)

    years = [_year_row(a, y, ds) for y in range(1, a.hold_years + 1)]

    # Exit: value the forward (year hold+1) NOI at the exit cap rate.
    forward_noi = _year_row(a, a.hold_years + 1, 0.0).noi
    gross_sale = forward_noi / a.exit_cap_rate
    selling_costs = gross_sale * a.selling_costs_rate
    payoff = (remaining_balance(loan.amount, loan.annual_rate, loan.term_years,
                                a.hold_years * loan.periods_per_year,
                                loan.periods_per_year, loan.interest_only_years)
              if loan else 0.0)
    sale = SaleSummary(
        year=a.hold_years,
        gross_sale_price=gross_sale,
        selling_costs=selling_costs,
        loan_payoff=payoff,
        net_sale_proceeds_unlevered=gross_sale - selling_costs,
        net_sale_proceeds_levered=gross_sale - selling_costs - payoff,
    )

    total_cost = a.purchase_price + a.acquisition_costs
    equity = total_cost - (loan.amount if loan else 0.0)
    if equity <= 0:
        raise ValueError("loan amount cannot exceed total acquisition cost")

    unlevered = [-total_cost] + [y.cash_flow_before_debt for y in years]
    unlevered[-1] += sale.net_sale_proceeds_unlevered
    levered = [-equity] + [y.cash_flow_after_debt for y in years]
    levered[-1] += sale.net_sale_proceeds_levered

    y1 = years[0]
    result_metrics = {
        "entry_cap_rate": m.cap_rate(y1.noi, a.purchase_price),
        "gross_rent_multiplier": m.gross_rent_multiplier(a.purchase_price, y1.gross_potential_income),
        "operating_expense_ratio": m.operating_expense_ratio(y1.operating_expenses, y1.effective_gross_income),
        "noi_year1": y1.noi,
        "unlevered_irr": irr(unlevered),
        "levered_irr": irr(levered),
        "unlevered_npv": npv(a.discount_rate, unlevered),
        "levered_npv": npv(a.discount_rate, levered),
        "equity_multiple": m.equity_multiple(sum(levered[1:]), equity),
        "cash_on_cash_year1": m.cash_on_cash(y1.cash_flow_after_debt, equity),
        "equity_invested": equity,
        "total_acquisition_cost": total_cost,
    }
    if loan:
        result_metrics.update({
            "annual_debt_service": ds,
            "dscr_year1": m.dscr(y1.noi, ds),
            "ltv": m.ltv(loan.amount, a.purchase_price),
            "debt_yield": m.debt_yield(y1.noi, loan.amount),
            "break_even_occupancy": m.break_even_occupancy(
                y1.operating_expenses + y1.capex_reserve, ds, y1.gross_potential_income),
            "monthly_payment_amortizing": loan_payment(
                loan.amount, loan.annual_rate,
                loan.term_years - loan.interest_only_years, loan.periods_per_year),
        })

    return ProForma(a, years, sale, equity, unlevered, levered, result_metrics)
