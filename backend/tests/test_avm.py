import math

import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app
from finance_core import avm

client = TestClient(app)


class TestRegression:
    def test_recovers_known_loglog_relationship(self):
        # price = 1_000_000 * area**0.8  → intercept ln(1e6), slope 0.8, r2 1.0
        areas = [100, 150, 200, 250, 300, 350]
        prices = [1_000_000 * a ** 0.8 for a in areas]
        reg = avm.fit_loglog(areas, prices)
        assert reg.slope == pytest.approx(0.8, abs=1e-9)
        assert reg.intercept == pytest.approx(math.log(1_000_000), abs=1e-9)
        assert reg.r_squared == pytest.approx(1.0, abs=1e-12)
        pred = avm.predict(reg, 275)
        assert pred["estimate"] == pytest.approx(1_000_000 * 275 ** 0.8, rel=1e-9)

    def test_prediction_interval_brackets_and_is_asymmetric(self):
        areas = [100, 120, 150, 180, 210, 260, 300]
        prices = [42e6, 47e6, 55e6, 61e6, 68e6, 80e6, 88e6]
        reg = avm.fit_loglog(areas, prices)
        pred = avm.predict(reg, 200)
        assert pred["lower"] < pred["estimate"] < pred["upper"]
        # log-space interval → wider on the upside
        assert (pred["upper"] - pred["estimate"]) > (pred["estimate"] - pred["lower"])

    def test_interval_widens_with_noise(self):
        areas = [100, 140, 180, 220, 260, 300, 340]
        clean = [avm.predict(avm.fit_loglog(areas, [1e6 * a for a in areas]), 200)]
        noisy_prices = [1e6 * a * (1.4 if i % 2 else 0.6) for i, a in enumerate(areas)]
        noisy = avm.predict(avm.fit_loglog(areas, noisy_prices), 200)
        clean_width = clean[0]["upper"] - clean[0]["lower"]
        assert (noisy["upper"] - noisy["lower"]) > clean_width

    def test_rejects_too_few_points(self):
        with pytest.raises(ValueError):
            avm.fit_loglog([100, 200], [1e6, 2e6])

    def test_rejects_identical_areas(self):
        with pytest.raises(ValueError):
            avm.fit_loglog([200, 200, 200, 200], [1e6, 1.1e6, 0.9e6, 1e6])

    def test_confidence_grades(self):
        assert avm.confidence(4, 0.9) == "low"        # too few
        assert avm.confidence(12, 0.8) == "high"
        assert avm.confidence(8, 0.5) == "medium"
        assert avm.confidence(8, 0.1) == "low"        # poor fit


class TestService:
    @pytest.fixture(autouse=True)
    def isolated_db(self, tmp_path, monkeypatch):
        monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")

    def _seed(self, pairs, **over):
        from app import comps
        for area, price in pairs:
            comps.add_comp(dict(kind="sale", use="residential", region="Dar es Salaam",
                                district="Kinondoni", price=price, currency="TZS",
                                area_sqm=area, observed_date="2026-03",
                                source="test", contributor="t", notes="", **over))

    def test_regresses_with_enough_comps(self):
        from app import avm_service
        self._seed([(250, 350e6), (290, 380e6), (310, 420e6), (335, 460e6),
                    (350, 505e6), (240, 340e6)])
        out = avm_service.estimate(320, {"kind": "sale", "district": "Kinondoni"})
        assert out["method"] == "hedonic_loglog_regression"
        assert out["lower"] < out["estimate"] < out["upper"]
        assert out["sample_size"] == 6
        assert out["size_elasticity"] is not None

    def test_falls_back_to_median_when_thin(self):
        from app import avm_service
        self._seed([(300, 400e6), (320, 430e6)])  # only 2
        out = avm_service.estimate(310, {"kind": "sale"})
        assert out["method"] == "median_unit_price"
        assert out["estimate"] is not None

    def test_insufficient_evidence(self):
        from app import avm_service
        out = avm_service.estimate(300, {"district": "Nowhere"})
        assert out["method"] == "insufficient_evidence"
        assert out["estimate"] is None
        assert out["confidence"] == "low"


class TestAPI:
    @pytest.fixture(autouse=True)
    def isolated_db(self, tmp_path, monkeypatch):
        monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")

    def test_endpoint_regression(self):
        from scripts import seed_comps
        seed_comps.main()  # 5 Kinondoni residential sales + others
        res = client.post("/api/avm", json={"area_sqm": 320, "kind": "sale",
                                            "use": "residential", "district": "Kinondoni"})
        assert res.status_code == 200
        body = res.json()
        assert body["estimate"] > 0
        assert body["lower"] < body["estimate"] < body["upper"]
        assert "not a valuation" in body["note"].lower()

    def test_endpoint_validation(self):
        assert client.post("/api/avm", json={"area_sqm": -5}).status_code == 422
