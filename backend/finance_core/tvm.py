"""Time-value-of-money primitives: NPV, IRR, XNPV, XIRR, MIRR."""

from __future__ import annotations

from datetime import date
from typing import Optional, Sequence


def npv(rate: float, cashflows: Sequence[float]) -> float:
    """Net present value of periodic cash flows.

    cashflows[0] occurs at t=0 (not discounted), cashflows[t] at end of period t.
    Note: this is Excel's NPV(rate, cf[1:]) + cf[0] convention.
    """
    if rate <= -1.0:
        raise ValueError("rate must be greater than -100%")
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def irr(cashflows: Sequence[float], low: float = -0.9999, high: float = 100.0,
        tol: float = 1e-9, max_iter: int = 200) -> Optional[float]:
    """Internal rate of return via bisection. Returns None when no sign change
    exists on [low, high] (e.g. all-positive or all-negative cash flows)."""
    if len(cashflows) < 2:
        return None
    f_low = npv(low, cashflows)
    f_high = npv(high, cashflows)
    if f_low * f_high > 0:
        return None
    for _ in range(max_iter):
        mid = (low + high) / 2.0
        f_mid = npv(mid, cashflows)
        if abs(f_mid) < tol or (high - low) / 2.0 < tol:
            return mid
        if f_low * f_mid < 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2.0


def xnpv(rate: float, cashflows: Sequence[tuple[date, float]]) -> float:
    """NPV of dated cash flows, discounted on an actual/365 basis (Excel XNPV)."""
    if rate <= -1.0:
        raise ValueError("rate must be greater than -100%")
    if not cashflows:
        return 0.0
    d0 = min(d for d, _ in cashflows)
    return sum(cf / (1.0 + rate) ** ((d - d0).days / 365.0) for d, cf in cashflows)


def xirr(cashflows: Sequence[tuple[date, float]], low: float = -0.9999,
         high: float = 100.0, tol: float = 1e-9, max_iter: int = 200) -> Optional[float]:
    """IRR of dated cash flows (Excel XIRR), via bisection."""
    if len(cashflows) < 2:
        return None
    f_low = xnpv(low, cashflows)
    f_high = xnpv(high, cashflows)
    if f_low * f_high > 0:
        return None
    for _ in range(max_iter):
        mid = (low + high) / 2.0
        f_mid = xnpv(mid, cashflows)
        if abs(f_mid) < tol or (high - low) / 2.0 < tol:
            return mid
        if f_low * f_mid < 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2.0


def mirr(cashflows: Sequence[float], finance_rate: float, reinvest_rate: float) -> Optional[float]:
    """Modified IRR (Excel MIRR): negatives discounted at finance_rate,
    positives compounded forward at reinvest_rate."""
    n = len(cashflows)
    if n < 2:
        return None
    pv_neg = sum(cf / (1.0 + finance_rate) ** t for t, cf in enumerate(cashflows) if cf < 0)
    fv_pos = sum(cf * (1.0 + reinvest_rate) ** (n - 1 - t) for t, cf in enumerate(cashflows) if cf > 0)
    if pv_neg == 0 or fv_pos == 0:
        return None
    return (fv_pos / -pv_neg) ** (1.0 / (n - 1)) - 1.0
