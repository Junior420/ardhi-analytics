"""AVM service: fit the hedonic model on the subject's comparable segment,
falling back to the median unit-price indication when evidence is too thin."""

from __future__ import annotations

from finance_core import avm

from . import comps

_MIN_REGRESSION = 6   # below this, a two-parameter fit overfits — use the median


def estimate(area_sqm: float, filters: dict) -> dict:
    """Statistical value estimate for a subject property.

    filters: kind/use/region/district/since — the market segment to draw
    comparables from (same shape as comps.stats)."""
    if area_sqm <= 0:
        raise ValueError("area_sqm must be positive")

    records = comps.list_comps(filters, limit=500)
    priced = [(c["area_sqm"], c["price"]) for c in records if c["area_sqm"]]
    n = len(priced)

    base = {"area_sqm": area_sqm, "sample_size": n, "filters": filters,
            "note": ("AVM is a statistical cross-check, not a valuation. "
                     "A registered valuer must certify statutory valuations.")}

    if n < _MIN_REGRESSION:
        # Not enough to regress — reuse the evidence-based median indication.
        ind = comps.indicate_value(area_sqm, filters)
        base.update({
            "method": "median_unit_price" if ind["indicated_value"] else "insufficient_evidence",
            "estimate": ind["indicated_value"],
            "lower": ind.get("indicated_range", [None, None])[0],
            "upper": ind.get("indicated_range", [None, None])[1],
            "confidence": ind["stats"]["confidence"] if ind["indicated_value"] else "low",
            "r_squared": None,
            "size_elasticity": None,
        })
        return base

    areas = [a for a, _ in priced]
    prices = [p for _, p in priced]
    try:
        reg = avm.fit_loglog(areas, prices)
        pred = avm.predict(reg, area_sqm)
    except ValueError:
        # Degenerate segment (e.g. all identical areas) — median fallback.
        ind = comps.indicate_value(area_sqm, filters)
        base.update({
            "method": "median_unit_price", "estimate": ind["indicated_value"],
            "lower": ind.get("indicated_range", [None, None])[0],
            "upper": ind.get("indicated_range", [None, None])[1],
            "confidence": ind["stats"]["confidence"], "r_squared": None,
            "size_elasticity": None,
        })
        return base

    base.update({
        "method": "hedonic_loglog_regression",
        "estimate": pred["estimate"],
        "lower": pred["lower"],
        "upper": pred["upper"],
        "implied_unit_price": pred["implied_unit_price"],
        "size_elasticity": pred["size_elasticity"],
        "r_squared": pred["r_squared"],
        "confidence": avm.confidence(reg.n, reg.r_squared),
    })
    return base
