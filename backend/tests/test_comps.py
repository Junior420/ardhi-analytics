import pytest
from fastapi.testclient import TestClient

from app import comps, store
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")


@pytest.fixture
def auth_headers():
    reg = client.post("/api/auth/register",
                      json={"email": "comps@example.com", "password": "s3cretpass"}).json()
    return {"Authorization": f"Bearer {reg['access_token']}"}


def comp(**overrides):
    base = dict(kind="sale", use="residential", region="Dar es Salaam",
                district="Kinondoni", price=400_000_000, currency="TZS",
                area_sqm=320.0, observed_date="2026-03", source="test agency",
                contributor="tester", notes="")
    base.update(overrides)
    return base


class TestStorage:
    def test_add_and_list(self):
        comps.add_comp(comp())
        comps.add_comp(comp(district="Ilala", price=300_000_000))
        assert len(comps.list_comps({})) == 2
        assert len(comps.list_comps({"district": "Kinondoni"})) == 1
        assert len(comps.list_comps({"district": "kinondoni"})) == 1  # case-insensitive

    def test_since_filter(self):
        comps.add_comp(comp(observed_date="2024-01"))
        comps.add_comp(comp(observed_date="2026-05"))
        assert len(comps.list_comps({"since": "2025-01"})) == 1

    def test_delete(self):
        rec = comps.add_comp(comp())
        assert comps.delete_comp(rec["id"]) is True
        assert comps.delete_comp(rec["id"]) is False

    def test_rejects_bad_kind(self):
        with pytest.raises(Exception):
            comps.add_comp(comp(kind="lease"))


class TestStats:
    def test_unit_price_median(self):
        # Unit prices: 1.0m, 1.2m, 1.4m per m² → median 1.2m
        comps.add_comp(comp(price=100_000_000, area_sqm=100))
        comps.add_comp(comp(price=120_000_000, area_sqm=100))
        comps.add_comp(comp(price=140_000_000, area_sqm=100))
        s = comps.stats({"kind": "sale"})
        assert s["unit_price_median"] == pytest.approx(1_200_000)
        assert s["count_with_area"] == 3

    def test_confidence_grades(self):
        for price in (100, 101, 102, 99, 100):
            comps.add_comp(comp(price=price * 1_000_000, area_sqm=100))
        assert comps.stats({})["confidence"] == "high"  # n=5, tight

        comps.add_comp(comp(price=500_000_000, area_sqm=100))  # wild outlier
        assert comps.stats({})["confidence"] in ("medium", "low")

    def test_no_area_data(self):
        comps.add_comp(comp(area_sqm=None))
        s = comps.stats({})
        assert s["count"] == 1 and s["count_with_area"] == 0
        assert s["confidence"] == "low"


class TestIndication:
    def test_indicated_value(self):
        comps.add_comp(comp(price=100_000_000, area_sqm=100))
        comps.add_comp(comp(price=120_000_000, area_sqm=100))
        comps.add_comp(comp(price=140_000_000, area_sqm=100))
        out = comps.indicate_value(250, {"kind": "sale"})
        assert out["indicated_value"] == pytest.approx(1_200_000 * 250)
        assert "Not a valuation" in out["note"]

    def test_insufficient_evidence(self):
        out = comps.indicate_value(250, {"district": "Nowhere"})
        assert out["indicated_value"] is None

    def test_bad_area(self):
        with pytest.raises(ValueError):
            comps.indicate_value(0, {})


class TestAPI:
    def test_crud_and_stats_flow(self, auth_headers):
        created = client.post("/api/comps", json=comp(), headers=auth_headers).json()
        assert "id" in created

        listed = client.get("/api/comps", params={"district": "Kinondoni"}).json()
        assert len(listed) == 1

        s = client.get("/api/comps/stats", params={"kind": "sale"}).json()
        assert s["count"] == 1

        ind = client.post("/api/comps/indicate",
                          json={"area_sqm": 250, "kind": "sale"}).json()
        assert ind["indicated_value"] == pytest.approx(400_000_000 / 320 * 250)

        assert client.delete(f"/api/comps/{created['id']}", headers=auth_headers).status_code == 200
        assert client.delete(f"/api/comps/{created['id']}", headers=auth_headers).status_code == 404

    def test_validation(self, auth_headers):
        assert client.post("/api/comps", json=comp(price=-5), headers=auth_headers).status_code == 422
        assert client.post("/api/comps", json=comp(observed_date="March"), headers=auth_headers).status_code == 422

    def test_seed_script(self):
        from scripts import seed_comps
        seed_comps.main()
        s = client.get("/api/comps/stats",
                       params={"kind": "sale", "use": "residential",
                               "district": "Kinondoni"}).json()
        assert s["count"] == 5
        assert s["confidence"] in ("high", "medium")
        listed = client.get("/api/comps").json()
        assert all("NOT real transactions" in c["source"] for c in listed
                   if c["contributor"] == "sample-data")
