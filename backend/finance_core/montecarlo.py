"""Monte Carlo simulation over pro forma assumptions.

Draws Gaussian shocks on the same parameters the sensitivity module perturbs
(reusing its shift/clamp logic), re-runs the pro forma for each draw, and
returns the resulting return distributions. Pure stdlib, seedable, and
deterministic for a given seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional, Sequence

from .projections import Assumptions, build_pro_forma
from .sensitivity import shift


@dataclass(frozen=True)
class ParamDist:
    param: str
    kind: str       # "relative" | "absolute" (same semantics as sensitivity.shift)
    sd: float       # standard deviation of the Gaussian shock


DEFAULT_DISTS: tuple[ParamDist, ...] = (
    ParamDist("gross_rent_annual", "relative", 0.07),
    ParamDist("operating_expenses_annual", "relative", 0.07),
    ParamDist("vacancy_rate", "absolute", 0.02),
    ParamDist("rent_growth", "absolute", 0.01),
    ParamDist("expense_growth", "absolute", 0.01),
    ParamDist("exit_cap_rate", "absolute", 0.005),
    ParamDist("loan.annual_rate", "absolute", 0.01),
)


def _percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolation percentile on pre-sorted values, p in [0, 100]."""
    if not sorted_values:
        raise ValueError("no values")
    k = (len(sorted_values) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = k - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def _summary(values: list[float], prob_below: dict[str, float]) -> dict:
    v = sorted(values)
    n = len(v)
    mean = sum(v) / n
    std = (sum((x - mean) ** 2 for x in v) / (n - 1)) ** 0.5 if n > 1 else 0.0
    out = {
        "mean": mean, "std": std, "min": v[0], "max": v[-1],
        "p5": _percentile(v, 5), "p25": _percentile(v, 25),
        "median": _percentile(v, 50),
        "p75": _percentile(v, 75), "p95": _percentile(v, 95),
    }
    for label, threshold in prob_below.items():
        out[label] = sum(1 for x in v if x < threshold) / n
    return out


def _histogram(values: list[float], bins: int = 20) -> dict:
    lo, hi = min(values), max(values)
    if hi == lo:
        return {"bin_edges": [lo, hi], "counts": [len(values)]}
    width = (hi - lo) / bins
    counts = [0] * bins
    for x in values:
        idx = min(int((x - lo) / width), bins - 1)
        counts[idx] += 1
    return {"bin_edges": [lo + i * width for i in range(bins + 1)], "counts": counts}


def simulate(a: Assumptions, n: int = 1000, seed: Optional[int] = None,
             dists: Sequence[ParamDist] = DEFAULT_DISTS) -> dict:
    """Return distributions of IRR, NPV, and equity multiple over n draws.

    Draws where the IRR has no solution (no sign change in the cash flows)
    are excluded from the IRR distribution but still counted in NPV/equity
    multiple; their count is reported as irr_undefined.
    """
    if n < 2:
        raise ValueError("n must be at least 2")
    rng = random.Random(seed)
    metric = "levered_irr" if a.loan else "unlevered_irr"
    npv_key = "levered_npv" if a.loan else "unlevered_npv"

    base = build_pro_forma(a)
    irrs: list[float] = []
    npvs: list[float] = []
    multiples: list[float] = []
    irr_undefined = 0

    active = [d for d in dists if not (d.param == "loan.annual_rate" and a.loan is None)]
    for _ in range(n):
        trial = a
        for d in active:
            trial = shift(trial, d.param, d.kind, rng.gauss(0.0, d.sd))
        try:
            pf = build_pro_forma(trial)
        except ValueError:
            # a draw pushed assumptions out of the valid domain; skip it
            irr_undefined += 1
            continue
        npvs.append(pf.metrics[npv_key])
        multiples.append(pf.metrics["equity_multiple"])
        irr = pf.metrics[metric]
        if irr is None:
            irr_undefined += 1
        else:
            irrs.append(irr)

    if not irrs:
        raise ValueError("no draw produced a defined IRR; check the assumptions")

    return {
        "n": n,
        "n_effective": len(irrs),
        "irr_undefined": irr_undefined,
        "seed": seed,
        "metric": metric,
        "base_irr": base.metrics[metric],
        "irr": _summary(irrs, {"prob_below_zero": 0.0,
                               "prob_below_discount_rate": a.discount_rate}),
        "npv": _summary(npvs, {"prob_below_zero": 0.0}),
        "equity_multiple": _summary(multiples, {"prob_below_one": 1.0}),
        "histogram": _histogram(irrs),
        "distributions": [d.__dict__ for d in active],
    }
