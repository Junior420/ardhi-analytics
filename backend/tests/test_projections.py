"""Pro forma engine tests: internal consistency + hand-verifiable cases."""

import pytest

from finance_core import irr, npv
from finance_core.projections import Assumptions, LoanTerms, build_pro_forma


def simple_deal(**overrides) -> Assumptions:
    base = dict(
        purchase_price=1_000_000.0,
        gross_rent_annual=120_000.0,
        acquisition_costs=20_000.0,
        vacancy_rate=0.05,
        operating_expenses_annual=34_000.0,
        rent_growth=0.0,
        expense_growth=0.0,
        capex_reserve_rate=0.0,
        hold_years=5,
        exit_cap_rate=0.08,
        selling_costs_rate=0.0,
        discount_rate=0.10,
        loan=None,
    )
    base.update(overrides)
    return Assumptions(**base)


class TestUnlevered:
    def test_flat_deal_hand_computed(self):
        # EGI = 114,000; NOI = 80,000 every year (no growth).
        # Sale = 80,000 / 0.08 = 1,000,000. Outlay = 1,020,000.
        pf = build_pro_forma(simple_deal())
        assert pf.years[0].noi == pytest.approx(80_000)
        assert pf.sale.gross_sale_price == pytest.approx(1_000_000)
        assert pf.unlevered_cashflows == pytest.approx(
            [-1_020_000, 80_000, 80_000, 80_000, 80_000, 1_080_000])
        # Metrics recomputed independently from those flows
        assert pf.metrics["unlevered_irr"] == pytest.approx(irr(pf.unlevered_cashflows), abs=1e-9)
        assert pf.metrics["unlevered_npv"] == pytest.approx(npv(0.10, pf.unlevered_cashflows), abs=1e-6)
        assert pf.metrics["entry_cap_rate"] == pytest.approx(0.08)

    def test_growth_compounds(self):
        pf = build_pro_forma(simple_deal(rent_growth=0.10, hold_years=3))
        assert pf.years[2].gross_potential_income == pytest.approx(120_000 * 1.21)


class TestLevered:
    def test_leverage_amplifies_positive_spread(self):
        loan = LoanTerms(amount=600_000, annual_rate=0.06, term_years=20)
        unlev = build_pro_forma(simple_deal())
        lev = build_pro_forma(simple_deal(loan=loan))
        # Cap rate 8% > 6% borrowing cost → positive leverage raises IRR
        assert lev.metrics["levered_irr"] > unlev.metrics["unlevered_irr"]
        assert lev.equity_invested == pytest.approx(420_000)
        assert lev.metrics["dscr_year1"] == pytest.approx(
            80_000 / lev.metrics["annual_debt_service"])

    def test_exit_pays_off_remaining_balance(self):
        loan = LoanTerms(amount=600_000, annual_rate=0.06, term_years=20)
        pf = build_pro_forma(simple_deal(loan=loan))
        assert pf.sale.net_sale_proceeds_levered == pytest.approx(
            pf.sale.gross_sale_price - pf.sale.selling_costs - pf.sale.loan_payoff)
        assert 0 < pf.sale.loan_payoff < 600_000

    def test_loan_exceeding_cost_rejected(self):
        with pytest.raises(ValueError):
            build_pro_forma(simple_deal(
                loan=LoanTerms(amount=1_100_000, annual_rate=0.06, term_years=20)))


class TestValidation:
    def test_bad_hold_years(self):
        with pytest.raises(ValueError):
            build_pro_forma(simple_deal(hold_years=0))

    def test_bad_exit_cap(self):
        with pytest.raises(ValueError):
            build_pro_forma(simple_deal(exit_cap_rate=0))
