"""Valuation approaches: income (direct cap + DCF) and sales comparison.

Cost approach lands in a later phase (needs construction cost data).
Outputs are opinion-of-value inputs for a professional; statutory valuations
require a registered valuer's sign-off.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .projections import Assumptions, build_pro_forma
from .tvm import npv


def direct_capitalization(stabilized_noi: float, market_cap_rate: float) -> float:
    if market_cap_rate <= 0:
        raise ValueError("market cap rate must be positive")
    return stabilized_noi / market_cap_rate


def dcf_value(a: Assumptions) -> float:
    """Present value of the unlevered operating cash flows plus net sale
    proceeds, at the discount rate — i.e. what the asset is worth today,
    independent of the asking price in `a`."""
    pf = build_pro_forma(a)
    flows = [0.0] + list(pf.unlevered_cashflows[1:])  # drop the purchase outlay
    return npv(a.discount_rate, flows)


@dataclass(frozen=True)
class Comparable:
    """A comparable sale. Adjustments are signed fractions of the sale price
    (e.g. +0.05 = subject is 5% better on that attribute), per the standard
    adjustment-grid convention."""
    name: str
    sale_price: float
    adjustments: dict[str, float] = field(default_factory=dict)
    weight: float = 1.0


@dataclass(frozen=True)
class SalesComparisonResult:
    adjusted: list[dict]
    reconciled_value: float
    min_value: float
    max_value: float
    gross_adjustment_warning: list[str]


def sales_comparison(comps: list[Comparable],
                     gross_adjustment_limit: float = 0.25) -> SalesComparisonResult:
    """Adjust each comparable toward the subject and reconcile by weight.

    Comps whose gross (absolute-sum) adjustments exceed the limit are flagged:
    heavily adjusted comps are weak evidence.
    """
    if not comps:
        raise ValueError("at least one comparable is required")
    if any(c.sale_price <= 0 for c in comps):
        raise ValueError("comparable sale prices must be positive")
    if all(c.weight <= 0 for c in comps):
        raise ValueError("at least one comparable needs a positive weight")

    adjusted, warnings = [], []
    for c in comps:
        net = sum(c.adjustments.values())
        gross = sum(abs(v) for v in c.adjustments.values())
        value = c.sale_price * (1.0 + net)
        if gross > gross_adjustment_limit:
            warnings.append(
                f"{c.name}: gross adjustments {gross:.0%} exceed {gross_adjustment_limit:.0%} — weak comparable")
        adjusted.append({"name": c.name, "sale_price": c.sale_price,
                         "net_adjustment": net, "gross_adjustment": gross,
                         "adjusted_value": value, "weight": max(c.weight, 0.0)})

    total_w = sum(x["weight"] for x in adjusted)
    reconciled = sum(x["adjusted_value"] * x["weight"] for x in adjusted) / total_w
    values = [x["adjusted_value"] for x in adjusted]
    return SalesComparisonResult(adjusted, reconciled, min(values), max(values), warnings)


def reconcile_approaches(values: dict[str, Optional[float]],
                         weights: Optional[dict[str, float]] = None) -> dict:
    """Weight the available approach values into a single opinion of value."""
    available = {k: v for k, v in values.items() if v is not None and v > 0}
    if not available:
        raise ValueError("no valuation approach produced a value")
    w = {k: (weights or {}).get(k, 1.0) for k in available}
    total = sum(w.values())
    final = sum(available[k] * w[k] for k in available) / total
    return {"approaches": available, "weights": w, "reconciled_value": final}
