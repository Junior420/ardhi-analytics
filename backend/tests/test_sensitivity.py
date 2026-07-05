import pytest

from finance_core import run_scenarios, tornado, two_way_grid
from finance_core.projections import Assumptions, LoanTerms

from tests.test_projections import simple_deal


def levered_deal(**overrides):
    return simple_deal(loan=LoanTerms(amount=600_000, annual_rate=0.06, term_years=20),
                       **overrides)


class TestScenarios:
    def test_ordering(self):
        out = run_scenarios(levered_deal())
        pess = out["pessimistic"].metrics["levered_irr"]
        base = out["base"].metrics["levered_irr"]
        opt = out["optimistic"].metrics["levered_irr"]
        assert pess < base < opt

    def test_base_matches_direct_run(self):
        from finance_core import build_pro_forma
        a = levered_deal()
        assert run_scenarios(a)["base"].metrics["levered_irr"] == pytest.approx(
            build_pro_forma(a).metrics["levered_irr"])


class TestTornado:
    def test_downside_below_upside(self):
        for row in tornado(levered_deal()):
            assert row["downside"] <= row["base"] <= row["upside"]

    def test_sorted_by_swing(self):
        swings = [r["swing"] for r in tornado(levered_deal())]
        assert swings == sorted(swings, reverse=True)

    def test_loan_rate_skipped_when_unlevered(self):
        params = {r["param"] for r in tornado(simple_deal())}
        assert "loan.annual_rate" not in params

    def test_unlevered_falls_back_to_unlevered_irr(self):
        rows = tornado(simple_deal())
        assert rows and all(r["base"] is not None for r in rows)


class TestGrid:
    def test_shape_and_monotonicity(self):
        out = two_way_grid(levered_deal(),
                           "exit_cap_rate", [0.07, 0.08, 0.09],
                           "rent_growth", [0.0, 0.02],
                           metric="levered_irr")
        assert len(out["matrix"]) == 3 and len(out["matrix"][0]) == 2
        # Lower exit cap (higher sale price) → higher IRR, more growth → higher IRR
        assert out["matrix"][0][0] > out["matrix"][2][0]
        assert out["matrix"][1][1] > out["matrix"][1][0]
