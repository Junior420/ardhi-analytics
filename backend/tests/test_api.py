import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

DEAL = {
    "name": "Test deal",
    "purchase_price": 450_000_000,
    "gross_rent_annual": 54_000_000,
    "vacancy_rate": 0.07,
    "operating_expenses_annual": 12_000_000,
    "rent_growth": 0.06,
    "expense_growth": 0.05,
    "hold_years": 7,
    "exit_cap_rate": 0.09,
    "discount_rate": 0.14,
    "buyer_resident": False,
    "loan": {"ltv": 0.6, "annual_rate": 0.15, "term_years": 15},
}


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_rulepack_endpoint():
    assert client.get("/api/rulepack/tz").json()["jurisdiction"] == "TZ"
    assert client.get("/api/rulepack/xx").status_code == 404


def test_analyze():
    res = client.post("/api/analyze", json=DEAL)
    assert res.status_code == 200
    body = res.json()
    assert body["metrics"]["levered_irr"] is not None
    assert body["metrics"]["dscr_year1"] > 0
    assert len(body["years"]) == 7
    # Non-resident buyer must trigger the TIC flag
    assert any(f["id"] == "non_resident_buyer" for f in body["compliance_flags"])
    assert body["rulepack"]["status"] == "draft"


def test_analyze_validation():
    bad = dict(DEAL, purchase_price=-5)
    assert client.post("/api/analyze", json=bad).status_code == 422


def test_pdf_report():
    res = client.post("/api/report", json=DEAL)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"
    assert len(res.content) > 2000


def test_scenarios_endpoint():
    res = client.post("/api/scenarios", json=DEAL)
    assert res.status_code == 200
    scen = res.json()["scenarios"]
    assert scen["pessimistic"]["levered_irr"] < scen["optimistic"]["levered_irr"]


def test_sensitivity_endpoint():
    res = client.post("/api/sensitivity", json=DEAL)
    assert res.status_code == 200
    body = res.json()
    assert body["tornado"] and body["grid"]["matrix"]
    assert any(r["param"] == "loan.annual_rate" for r in body["tornado"])


def test_valuation_endpoint():
    req = {
        "stabilized_noi": 38_220_000,
        "market_cap_rate": 0.09,
        "deal": DEAL,
        "comparables": [
            {"name": "Comp A", "sale_price": 430_000_000, "adjustments": {"location": 0.05}},
            {"name": "Comp B", "sale_price": 470_000_000, "adjustments": {"size": -0.03}},
        ],
    }
    res = client.post("/api/valuation", json=req)
    assert res.status_code == 200
    body = res.json()
    assert set(body["approaches"]) == {"income_direct_cap", "income_dcf", "sales_comparison"}
    assert body["approaches"]["income_direct_cap"] == pytest.approx(38_220_000 / 0.09)
    assert body["reconciled_value"] > 0

    assert client.post("/api/valuation", json={}).status_code == 422


def test_deals_crud(tmp_path, monkeypatch):
    from app import store
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    reg = client.post("/api/auth/register",
                      json={"email": "t@example.com", "password": "s3cretpass"}).json()
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    created = client.post("/api/deals", json=DEAL, headers=h).json()
    assert created["name"] == DEAL["name"]

    deals = client.get("/api/deals", headers=h).json()
    assert any(d["id"] == created["id"] for d in deals)

    fetched = client.get(f"/api/deals/{created['id']}", headers=h).json()
    assert fetched["purchase_price"] == DEAL["purchase_price"]
    assert fetched["loan"]["ltv"] == DEAL["loan"]["ltv"]

    assert client.delete(f"/api/deals/{created['id']}", headers=h).status_code == 200
    assert client.get(f"/api/deals/{created['id']}", headers=h).status_code == 404
    assert client.delete(f"/api/deals/{created['id']}", headers=h).status_code == 404


def test_index_serves_ui():
    res = client.get("/")
    assert res.status_code == 200
    assert "Ardhi Analytics" in res.text
