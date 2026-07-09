"""Automated Valuation Model — a hedonic size regression on comparables.

Pure Python (no numpy/sklearn). Real estate prices scale non-linearly with
size — price per m² typically falls as area grows — so the model fits

    log(price) = a + b * log(area)

within the subject's market segment, then predicts the subject's value with a
95% prediction interval derived from the residual standard error. This is an
AVM in the classic sense: a statistical cross-check, never the sole basis for
a valuation (IVS treats AVMs exactly this way).

The caller (app.avm) decides when there's enough evidence to regress; this
module is the pure math and is exhaustively unit-tested.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# 95% two-sided Student-t critical values by degrees of freedom (n-2).
# Small-sample honesty: with few comps the interval must widen, not pretend
# to normality. df beyond the table falls back to the z-approximation.
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
        7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 12: 2.179, 15: 2.131,
        20: 2.086, 25: 2.060, 30: 2.042}


def _t_critical(df: int) -> float:
    if df <= 0:
        return float("inf")
    if df in _T95:
        return _T95[df]
    keys = sorted(_T95)
    if df < keys[-1]:
        # nearest tabulated df at or above (conservative — wider interval)
        for k in keys:
            if k >= df:
                return _T95[k]
    return 1.960  # large-sample normal approximation


@dataclass(frozen=True)
class Regression:
    n: int
    slope: float          # elasticity of price w.r.t. area (log-log)
    intercept: float
    r_squared: float
    residual_se: float    # standard error of the log-residuals
    mean_log_x: float
    ss_x: float           # sum of squared deviations of log(area)


def fit_loglog(areas: list[float], prices: list[float]) -> Regression:
    """Ordinary least squares of log(price) on log(area)."""
    if len(areas) != len(prices):
        raise ValueError("areas and prices must be the same length")
    n = len(areas)
    if n < 3:
        raise ValueError("need at least 3 observations to regress")
    if any(a <= 0 for a in areas) or any(p <= 0 for p in prices):
        raise ValueError("areas and prices must be positive")

    xs = [math.log(a) for a in areas]
    ys = [math.log(p) for p in prices]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_x = sum((x - mean_x) ** 2 for x in xs)
    if ss_x == 0:
        raise ValueError("all comparables have the same area — cannot regress")
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = ss_xy / ss_x
    intercept = mean_y - slope * mean_x

    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    sse = sum(r * r for r in residuals)
    ss_y = sum((y - mean_y) ** 2 for y in ys)
    r_squared = 1.0 - sse / ss_y if ss_y > 0 else 0.0
    residual_se = math.sqrt(sse / (n - 2)) if n > 2 else float("inf")

    return Regression(n, slope, intercept, r_squared, residual_se, mean_x, ss_x)


def predict(reg: Regression, area: float) -> dict:
    """Point estimate and 95% prediction interval for a subject of `area`.

    The interval is computed in log space (where the model is linear and
    errors are ~homoscedastic) then exponentiated back to currency, so the
    band is asymmetric — correctly wider on the upside."""
    if area <= 0:
        raise ValueError("area must be positive")
    log_x = math.log(area)
    log_pred = reg.intercept + reg.slope * log_x

    # Standard error of a single prediction (not just the mean response).
    se_pred = reg.residual_se * math.sqrt(
        1.0 + 1.0 / reg.n + (log_x - reg.mean_log_x) ** 2 / reg.ss_x)
    t = _t_critical(reg.n - 2)
    margin = t * se_pred

    point = math.exp(log_pred)
    return {
        "estimate": point,
        "lower": math.exp(log_pred - margin),
        "upper": math.exp(log_pred + margin),
        "implied_unit_price": point / area,
        "size_elasticity": reg.slope,
        "r_squared": reg.r_squared,
        "n": reg.n,
    }


def confidence(n: int, r_squared: float) -> str:
    """Evidence quality of the fit. Thin or poorly-fitting data is never
    presented as strong — mirrors the comparables-stats grading."""
    if n < 6:
        return "low"
    if n >= 10 and r_squared >= 0.6:
        return "high"
    if r_squared >= 0.4:
        return "medium"
    return "low"
