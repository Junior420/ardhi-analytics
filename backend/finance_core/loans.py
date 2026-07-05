"""Loan mathematics: payments, amortization schedules, balances."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Period:
    number: int
    payment: float
    interest: float
    principal: float
    balance: float


def payment(principal: float, annual_rate: float, term_years: float,
            periods_per_year: int = 12) -> float:
    """Level payment for a fully amortizing loan."""
    n = round(term_years * periods_per_year)
    if n <= 0:
        raise ValueError("term must be positive")
    if annual_rate == 0:
        return principal / n
    r = annual_rate / periods_per_year
    return principal * r / (1.0 - (1.0 + r) ** -n)


def amortization_schedule(principal: float, annual_rate: float, term_years: float,
                          periods_per_year: int = 12,
                          interest_only_years: float = 0.0) -> list[Period]:
    """Full period-by-period schedule.

    With an interest-only phase, the loan pays interest only for
    interest_only_years, then amortizes over the remaining term.
    """
    if interest_only_years >= term_years:
        raise ValueError("interest-only phase must be shorter than the term")
    r = annual_rate / periods_per_year
    io_periods = round(interest_only_years * periods_per_year)
    amort_years = term_years - interest_only_years
    amort_payment = payment(principal, annual_rate, amort_years, periods_per_year)

    schedule: list[Period] = []
    balance = principal
    total = round(term_years * periods_per_year)
    for k in range(1, total + 1):
        interest = balance * r
        if k <= io_periods:
            pay, princ = interest, 0.0
        else:
            pay = amort_payment
            princ = pay - interest
        balance = max(balance - princ, 0.0)
        schedule.append(Period(k, pay, interest, princ, balance))
    return schedule


def remaining_balance(principal: float, annual_rate: float, term_years: float,
                      after_periods: int, periods_per_year: int = 12,
                      interest_only_years: float = 0.0) -> float:
    """Outstanding balance after `after_periods` payments have been made."""
    if after_periods <= 0:
        return principal
    schedule = amortization_schedule(principal, annual_rate, term_years,
                                     periods_per_year, interest_only_years)
    if after_periods >= len(schedule):
        return 0.0
    return schedule[after_periods - 1].balance


def annual_debt_service(principal: float, annual_rate: float, term_years: float,
                        periods_per_year: int = 12,
                        interest_only_years: float = 0.0) -> float:
    """Debt service in the first year (interest-only phase aware)."""
    schedule = amortization_schedule(principal, annual_rate, term_years,
                                     periods_per_year, interest_only_years)
    return sum(p.payment for p in schedule[:periods_per_year])
