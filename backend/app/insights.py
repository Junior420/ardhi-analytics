"""Scenario, sensitivity, and valuation services over a DealInput."""

from __future__ import annotations

from finance_core import (
    Comparable, dcf_value, direct_capitalization, monte_carlo,
    reconcile_approaches, run_scenarios, sales_comparison, tornado, two_way_grid,
)

from .analysis import to_assumptions
from .schemas import ComparableInput, DealInput, ValuationRequest

# Fields worth surfacing per scenario in comparisons.
_SCENARIO_METRICS = ("levered_irr", "unlevered_irr", "levered_npv", "equity_multiple",
                     "cash_on_cash_year1", "dscr_year1", "noi_year1")


def scenarios(deal: DealInput) -> dict:
    a, _ = to_assumptions(deal)
    out = {}
    for name, pf in run_scenarios(a).items():
        out[name] = {k: pf.metrics.get(k) for k in _SCENARIO_METRICS}
    return {"scenarios": out}


def sensitivity(deal: DealInput) -> dict:
    a, _ = to_assumptions(deal)
    rows = tornado(a)

    # Two-way grid: exit cap x rent growth, centered on the deal's values.
    cap = deal.exit_cap_rate
    growth = deal.rent_growth
    grid = two_way_grid(
        a,
        "exit_cap_rate", [round(max(cap + d, 0.005), 4) for d in (-0.01, -0.005, 0, 0.005, 0.01)],
        "rent_growth", [round(growth + d, 4) for d in (-0.02, -0.01, 0, 0.01, 0.02)],
        metric="levered_irr" if deal.loan else "unlevered_irr",
    )
    return {"tornado": rows, "grid": grid}


def _to_comparable(c: ComparableInput) -> Comparable:
    return Comparable(name=c.name, sale_price=c.sale_price,
                      adjustments=c.adjustments, weight=c.weight)


def valuation(req: ValuationRequest) -> dict:
    values: dict = {}
    detail: dict = {}

    if req.stabilized_noi and req.market_cap_rate:
        values["income_direct_cap"] = direct_capitalization(req.stabilized_noi, req.market_cap_rate)

    if req.deal is not None:
        a, _ = to_assumptions(req.deal)
        values["income_dcf"] = dcf_value(a)

    if req.comparables:
        sc = sales_comparison([_to_comparable(c) for c in req.comparables])
        values["sales_comparison"] = sc.reconciled_value
        detail["sales_comparison"] = {
            "adjusted": sc.adjusted,
            "range": [sc.min_value, sc.max_value],
            "warnings": sc.gross_adjustment_warning,
        }

    reconciled = reconcile_approaches(values, req.approach_weights)
    return {**reconciled, "detail": detail,
            "note": "Opinion-of-value inputs only; statutory valuations require "
                    "a registered valuer under the Valuation and Valuers Registration Act, 2016."}


def simulate(deal: DealInput, n: int = 1000, seed: int | None = None) -> dict:
    a, _ = to_assumptions(deal)
    return monte_carlo(a, n=n, seed=seed)
