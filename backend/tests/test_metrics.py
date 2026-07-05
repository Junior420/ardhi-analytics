import pytest

from finance_core import (
    break_even_occupancy, cap_rate, cash_on_cash, debt_yield, dscr,
    equity_multiple, gross_rent_multiplier, ltv, noi, operating_expense_ratio,
)


def test_noi():
    assert noi(120_000, 45_000) == 75_000


def test_cap_rate():
    assert cap_rate(75_000, 1_000_000) == pytest.approx(0.075)
    with pytest.raises(ValueError):
        cap_rate(75_000, 0)


def test_grm():
    assert gross_rent_multiplier(1_000_000, 125_000) == pytest.approx(8.0)


def test_dscr():
    assert dscr(75_000, 60_000) == pytest.approx(1.25)


def test_ltv():
    assert ltv(700_000, 1_000_000) == pytest.approx(0.70)


def test_debt_yield():
    assert debt_yield(75_000, 700_000) == pytest.approx(0.10714, abs=1e-4)


def test_cash_on_cash():
    assert cash_on_cash(24_000, 300_000) == pytest.approx(0.08)


def test_equity_multiple():
    assert equity_multiple(600_000, 300_000) == pytest.approx(2.0)


def test_oer():
    assert operating_expense_ratio(45_000, 120_000) == pytest.approx(0.375)


def test_break_even_occupancy():
    # (opex 45k + debt 60k) / GPI 130k = 80.77%
    assert break_even_occupancy(45_000, 60_000, 130_000) == pytest.approx(0.8077, abs=1e-4)
