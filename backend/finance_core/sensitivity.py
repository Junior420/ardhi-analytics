"""Scenario and sensitivity analysis over pro forma assumptions.

Everything works by perturbing an Assumptions object and re-running
build_pro_forma — no separate math to drift out of sync with the engine.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from .projections import Assumptions, ProForma, build_pro_forma

# param -> (shift kind, [low delta, high delta])
# "relative": multiply the base value; "absolute": add to the base value.
DEFAULT_SHIFTS: dict[str, tuple[str, list[float]]] = {
    "gross_rent_annual": ("relative", [-0.10, 0.10]),
    "operating_expenses_annual": ("relative", [0.10, -0.10]),  # +10% opex is the downside
    "vacancy_rate": ("absolute", [0.05, -0.03]),
    "rent_growth": ("absolute", [-0.02, 0.02]),
    "exit_cap_rate": ("absolute", [0.01, -0.01]),              # higher exit cap is the downside
    "loan.annual_rate": ("absolute", [0.02, -0.02]),
}

SCENARIOS: dict[str, dict[str, tuple[str, float]]] = {
    "pessimistic": {
        "gross_rent_annual": ("relative", -0.10),
        "vacancy_rate": ("absolute", 0.05),
        "rent_growth": ("absolute", -0.02),
        "expense_growth": ("absolute", 0.01),
        "exit_cap_rate": ("absolute", 0.01),
    },
    "base": {},
    "optimistic": {
        "gross_rent_annual": ("relative", 0.05),
        "vacancy_rate": ("absolute", -0.02),
        "rent_growth": ("absolute", 0.01),
        "expense_growth": ("absolute", -0.01),
        "exit_cap_rate": ("absolute", -0.01),
    },
}


def _clamp(param: str, value: float) -> float:
    if param in ("vacancy_rate", "expense_growth", "rent_growth"):
        return min(max(value, -0.5 if "growth" in param else 0.0), 0.95)
    if param == "exit_cap_rate":
        return max(value, 0.005)
    if param == "loan.annual_rate":
        return max(value, 0.0)
    return max(value, 0.0)


def shift(a: Assumptions, param: str, kind: str, delta: float) -> Assumptions:
    """Return a copy of `a` with one parameter shifted."""
    if param == "loan.annual_rate":
        if a.loan is None:
            return a
        base = a.loan.annual_rate
        new = base * (1 + delta) if kind == "relative" else base + delta
        return replace(a, loan=replace(a.loan, annual_rate=_clamp(param, new)))
    base = getattr(a, param)
    new = base * (1 + delta) if kind == "relative" else base + delta
    return replace(a, **{param: _clamp(param, new)})


def apply_scenario(a: Assumptions, shifts: dict[str, tuple[str, float]]) -> Assumptions:
    for param, (kind, delta) in shifts.items():
        a = shift(a, param, kind, delta)
    return a


def run_scenarios(a: Assumptions,
                  scenarios: Optional[dict[str, dict]] = None) -> dict[str, ProForma]:
    return {name: build_pro_forma(apply_scenario(a, shifts))
            for name, shifts in (scenarios or SCENARIOS).items()}


def tornado(a: Assumptions,
            shifts: Optional[dict[str, tuple[str, list[float]]]] = None,
            metric: str = "levered_irr") -> list[dict]:
    """One-way sensitivity: for each parameter, the metric at its downside
    and upside shift. Sorted by impact (widest swing first)."""
    base_pf = build_pro_forma(a)
    fallback = "unlevered_irr" if metric == "levered_irr" and a.loan is None else metric
    base_val = base_pf.metrics.get(metric) or base_pf.metrics.get(fallback)

    rows = []
    for param, (kind, (down, up)) in (shifts or DEFAULT_SHIFTS).items():
        if param == "loan.annual_rate" and a.loan is None:
            continue
        low_pf = build_pro_forma(shift(a, param, kind, down))
        high_pf = build_pro_forma(shift(a, param, kind, up))
        low = low_pf.metrics.get(metric) or low_pf.metrics.get(fallback)
        high = high_pf.metrics.get(metric) or high_pf.metrics.get(fallback)
        if low is None or high is None:
            continue
        rows.append({
            "param": param,
            "kind": kind,
            "downside_delta": down,
            "upside_delta": up,
            "metric": metric,
            "base": base_val,
            "downside": low,
            "upside": high,
            "swing": abs(high - low),
        })
    rows.sort(key=lambda r: r["swing"], reverse=True)
    return rows


def two_way_grid(a: Assumptions, param_rows: str, row_values: list[float],
                 param_cols: str, col_values: list[float],
                 metric: str = "levered_irr") -> dict:
    """Metric matrix over absolute values of two parameters (e.g. exit cap
    rate x rent growth)."""
    def set_abs(base: Assumptions, param: str, value: float) -> Assumptions:
        if param == "loan.annual_rate":
            if base.loan is None:
                return base
            return replace(base, loan=replace(base.loan, annual_rate=value))
        return replace(base, **{param: value})

    matrix = []
    for rv in row_values:
        row = []
        for cv in col_values:
            pf = build_pro_forma(set_abs(set_abs(a, param_rows, rv), param_cols, cv))
            row.append(pf.metrics.get(metric))
        matrix.append(row)
    return {"row_param": param_rows, "row_values": row_values,
            "col_param": param_cols, "col_values": col_values,
            "metric": metric, "matrix": matrix}
