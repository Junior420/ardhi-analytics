import pytest
from fastapi.testclient import TestClient

from app.main import app
from finance_core import monte_carlo
from finance_core.montecarlo import ParamDist, _percentile
from finance_core.projections import LoanTerms

from tests.test_projections import simple_deal

client = TestClient(app)


def levered():
    return simple_deal(loan=LoanTerms(amount=600_000, annual_rate=0.06, term_years=20))


class TestPercentile:
    def test_known_values(self):
        v = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _percentile(v, 0) == 1.0
        assert _percentile(v, 50) == 3.0
        assert _percentile(v, 100) == 5.0
        assert _percentile(v, 25) == 2.0


class TestSimulate:
    def test_deterministic_for_seed(self):
        a = monte_carlo(levered(), n=300, seed=7)
        b = monte_carlo(levered(), n=300, seed=7)
        assert a["irr"] == b["irr"] and a["histogram"] == b["histogram"]

    def test_different_seeds_differ(self):
        a = monte_carlo(levered(), n=300, seed=1)
        b = monte_carlo(levered(), n=300, seed=2)
        assert a["irr"]["mean"] != b["irr"]["mean"]

    def test_median_near_base(self):
        out = monte_carlo(levered(), n=800, seed=3)
        assert out["irr"]["median"] == pytest.approx(out["base_irr"], abs=0.03)

    def test_percentiles_ordered_and_probs_valid(self):
        out = monte_carlo(levered(), n=400, seed=5)
        irr = out["irr"]
        assert irr["p5"] <= irr["p25"] <= irr["median"] <= irr["p75"] <= irr["p95"]
        for key in ("prob_below_zero", "prob_below_discount_rate"):
            assert 0.0 <= irr[key] <= 1.0
        assert sum(out["histogram"]["counts"]) == out["n_effective"]

    def test_wider_shocks_widen_distribution(self):
        tight = monte_carlo(levered(), n=400, seed=9,
                            dists=[ParamDist("gross_rent_annual", "relative", 0.02)])
        wide = monte_carlo(levered(), n=400, seed=9,
                           dists=[ParamDist("gross_rent_annual", "relative", 0.15)])
        assert wide["irr"]["std"] > tight["irr"]["std"]

    def test_unlevered_uses_unlevered_metric(self):
        out = monte_carlo(simple_deal(), n=200, seed=4)
        assert out["metric"] == "unlevered_irr"

    def test_rejects_tiny_n(self):
        with pytest.raises(ValueError):
            monte_carlo(levered(), n=1)


class TestAPI:
    DEAL = {"purchase_price": 450_000_000, "gross_rent_annual": 54_000_000,
            "vacancy_rate": 0.07, "operating_expenses_annual": 12_000_000,
            "rent_growth": 0.06, "expense_growth": 0.05, "hold_years": 7,
            "exit_cap_rate": 0.09, "discount_rate": 0.14,
            "loan": {"ltv": 0.6, "annual_rate": 0.15, "term_years": 15}}

    def test_endpoint(self):
        res = client.post("/api/montecarlo",
                          json={"deal": self.DEAL, "n": 300, "seed": 11})
        assert res.status_code == 200
        body = res.json()
        assert body["metric"] == "levered_irr"
        assert body["irr"]["p5"] < body["irr"]["p95"]
        assert len(body["histogram"]["counts"]) == 20

    def test_endpoint_reproducible(self):
        a = client.post("/api/montecarlo", json={"deal": self.DEAL, "n": 200, "seed": 1}).json()
        b = client.post("/api/montecarlo", json={"deal": self.DEAL, "n": 200, "seed": 1}).json()
        assert a["irr"] == b["irr"]

    def test_n_bounds_enforced(self):
        assert client.post("/api/montecarlo",
                           json={"deal": self.DEAL, "n": 50}).status_code == 422
