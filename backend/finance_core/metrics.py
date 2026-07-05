"""Standard real estate income and debt metrics."""

from __future__ import annotations


def noi(effective_gross_income: float, operating_expenses: float) -> float:
    """Net operating income. Excludes debt service, capex reserves, and taxes
    on income (per standard appraisal convention)."""
    return effective_gross_income - operating_expenses


def cap_rate(annual_noi: float, value: float) -> float:
    if value <= 0:
        raise ValueError("value must be positive")
    return annual_noi / value


def gross_rent_multiplier(price: float, gross_annual_rent: float) -> float:
    if gross_annual_rent <= 0:
        raise ValueError("gross rent must be positive")
    return price / gross_annual_rent


def dscr(annual_noi: float, annual_debt_service_: float) -> float:
    if annual_debt_service_ <= 0:
        raise ValueError("debt service must be positive")
    return annual_noi / annual_debt_service_


def ltv(loan_amount: float, value: float) -> float:
    if value <= 0:
        raise ValueError("value must be positive")
    return loan_amount / value


def debt_yield(annual_noi: float, loan_amount: float) -> float:
    if loan_amount <= 0:
        raise ValueError("loan amount must be positive")
    return annual_noi / loan_amount


def cash_on_cash(annual_pre_tax_cash_flow: float, equity_invested: float) -> float:
    if equity_invested <= 0:
        raise ValueError("equity must be positive")
    return annual_pre_tax_cash_flow / equity_invested


def equity_multiple(total_distributions: float, equity_invested: float) -> float:
    if equity_invested <= 0:
        raise ValueError("equity must be positive")
    return total_distributions / equity_invested


def operating_expense_ratio(operating_expenses: float, effective_gross_income: float) -> float:
    if effective_gross_income <= 0:
        raise ValueError("effective gross income must be positive")
    return operating_expenses / effective_gross_income


def break_even_occupancy(operating_expenses: float, annual_debt_service_: float,
                         gross_potential_income: float) -> float:
    """Occupancy at which income exactly covers opex + debt service."""
    if gross_potential_income <= 0:
        raise ValueError("gross potential income must be positive")
    return (operating_expenses + annual_debt_service_) / gross_potential_income
