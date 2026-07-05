"""finance_core — pure, deterministic real estate finance calculations.

No I/O, no framework imports. Every public function is unit-tested against
independently verified golden values (Excel / HP-12C / published tables).
"""

from .tvm import npv, irr, xnpv, xirr, mirr
from .loans import payment, amortization_schedule, remaining_balance, annual_debt_service
from .metrics import (
    noi,
    cap_rate,
    gross_rent_multiplier,
    dscr,
    ltv,
    debt_yield,
    cash_on_cash,
    equity_multiple,
    operating_expense_ratio,
    break_even_occupancy,
)
from .projections import build_pro_forma
from .montecarlo import simulate as monte_carlo
from .sensitivity import run_scenarios, tornado, two_way_grid
from .valuation import (
    Comparable,
    dcf_value,
    direct_capitalization,
    reconcile_approaches,
    sales_comparison,
)

__all__ = [
    "npv", "irr", "xnpv", "xirr", "mirr",
    "payment", "amortization_schedule", "remaining_balance", "annual_debt_service",
    "noi", "cap_rate", "gross_rent_multiplier", "dscr", "ltv", "debt_yield",
    "cash_on_cash", "equity_multiple", "operating_expense_ratio", "break_even_occupancy",
    "build_pro_forma",
    "monte_carlo", "run_scenarios", "tornado", "two_way_grid",
    "Comparable", "dcf_value", "direct_capitalization",
    "reconcile_approaches", "sales_comparison",
]
