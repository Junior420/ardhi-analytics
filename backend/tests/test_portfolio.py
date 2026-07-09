import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")


def auth():
    reg = client.post("/api/auth/register",
                      json={"email": "inv@example.com", "password": "s3cretpass"}).json()
    return {"Authorization": f"Bearer {reg['access_token']}"}


# A comfortably-covered financed deal (DSCR > 1) and a thin one (DSCR < 1).
STRONG = {"name": "Strong", "purchase_price": 500_000_000,
          "gross_rent_annual": 90_000_000, "operating_expenses_annual": 15_000_000,
          "hold_years": 7, "exit_cap_rate": 0.09, "discount_rate": 0.14,
          "loan": {"ltv": 0.5, "annual_rate": 0.12, "term_years": 15}}
THIN = {"name": "Thin", "purchase_price": 450_000_000,
        "gross_rent_annual": 54_000_000, "operating_expenses_annual": 12_000_000,
        "hold_years": 7, "exit_cap_rate": 0.09, "discount_rate": 0.14,
        "loan": {"ltv": 0.6, "annual_rate": 0.15, "term_years": 15}}


class TestSummary:
    def test_empty_portfolio(self):
        s = client.get("/api/portfolio/summary", headers=auth()).json()
        assert s["deal_count"] == 0
        assert s["total_equity_invested"] == 0
        assert s["equity_weighted_irr"] is None

    def test_rollup(self):
        h = auth()
        client.post("/api/deals", json=STRONG, headers=h)
        client.post("/api/deals", json=THIN, headers=h)
        s = client.get("/api/portfolio/summary", headers=h).json()
        assert s["deal_count"] == 2
        assert s["total_equity_invested"] > 0
        assert s["portfolio_dscr_year1"] is not None
        assert s["equity_weighted_irr"] is not None
        # exposure sums to total equity
        assert sum(s["exposure_by_use"].values()) == pytest.approx(s["total_equity_invested"])
        assert len(s["deals"]) == 2

    def test_requires_auth(self):
        assert client.get("/api/portfolio/summary").status_code == 401

    def test_only_own_deals(self):
        a = auth()
        client.post("/api/deals", json=STRONG, headers=a)
        b = client.post("/api/auth/register",
                        json={"email": "other@example.com", "password": "s3cretpass"}).json()
        bh = {"Authorization": f"Bearer {b['access_token']}"}
        assert client.get("/api/portfolio/summary", headers=bh).json()["deal_count"] == 0


class TestAlerts:
    def test_thin_deal_alerts_on_rate_shock(self):
        h = auth()
        client.post("/api/deals", json=THIN, headers=h)
        out = client.get("/api/portfolio/alerts?rate_bps=300&rent_pct=-10", headers=h).json()
        assert out["alert_count"] >= 1
        flags = out["alerts"][0]["flags"]
        assert any("DSCR" in f for f in flags)

    def test_no_shock_no_alert(self):
        h = auth()
        client.post("/api/deals", json=STRONG, headers=h)
        out = client.get("/api/portfolio/alerts?rate_bps=0&rent_pct=0", headers=h).json()
        # strong deal under no shock should not trip alerts
        assert out["alert_count"] == 0

    def test_shock_params_echoed(self):
        h = auth()
        out = client.get("/api/portfolio/alerts?rate_bps=150&rent_pct=-5", headers=h).json()
        assert out["shock"] == {"rate_bps": 150.0, "rent_pct": -5.0}


class TestActuals:
    def test_record_and_variance(self):
        h = auth()
        deal_id = client.post("/api/deals", json=THIN, headers=h).json()["id"]
        # year-1 projected GPI is 54,000,000; record a shortfall
        r = client.post(f"/api/deals/{deal_id}/actuals", headers=h,
                        json={"year": 1, "gross_rent_actual": 50_000_000,
                              "opex_actual": 13_000_000, "note": "two units vacant"})
        assert r.status_code == 200
        var = client.get(f"/api/deals/{deal_id}/actuals", headers=h).json()
        assert var["years_recorded"] == 1
        row = var["variance"][0]
        assert row["gross_rent"]["variance"] == pytest.approx(50_000_000 - 54_000_000)
        assert row["opex"]["variance"] == pytest.approx(13_000_000 - 12_000_000)
        assert row["note"] == "two units vacant"

    def test_actuals_require_ownership(self):
        h = auth()
        deal_id = client.post("/api/deals", json=THIN, headers=h).json()["id"]
        other = client.post("/api/auth/register",
                            json={"email": "x@example.com", "password": "s3cretpass"}).json()
        oh = {"Authorization": f"Bearer {other['access_token']}"}
        assert client.post(f"/api/deals/{deal_id}/actuals", headers=oh,
                           json={"year": 1, "gross_rent_actual": 1, "opex_actual": 1}
                           ).status_code == 404

    def test_year_beyond_horizon_flagged(self):
        h = auth()
        deal_id = client.post("/api/deals", json=THIN, headers=h).json()["id"]
        client.post(f"/api/deals/{deal_id}/actuals", headers=h,
                    json={"year": 20, "gross_rent_actual": 1, "opex_actual": 1})
        var = client.get(f"/api/deals/{deal_id}/actuals", headers=h).json()
        assert "error" in var["variance"][0]
