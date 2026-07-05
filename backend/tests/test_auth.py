import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")


def signup(email="user@example.com", password="s3cretpass"):
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    body = res.json()
    return body["user"], {"Authorization": f"Bearer {body['access_token']}"}


DEAL = {"purchase_price": 100_000_000, "gross_rent_annual": 12_000_000,
        "operating_expenses_annual": 3_000_000, "name": "Auth test deal"}


class TestAccounts:
    def test_first_user_is_admin(self):
        user, _ = signup()
        assert user["role"] == "admin"
        second, _ = signup("other@example.com")
        assert second["role"] == "member"

    def test_duplicate_email_rejected(self):
        signup()
        res = client.post("/api/auth/register",
                          json={"email": "user@example.com", "password": "s3cretpass"})
        assert res.status_code == 422

    def test_login_and_me(self):
        signup()
        res = client.post("/api/auth/login",
                          json={"email": "USER@example.com", "password": "s3cretpass"})
        assert res.status_code == 200
        token = res.json()["access_token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["email"] == "user@example.com"

    def test_wrong_password(self):
        signup()
        res = client.post("/api/auth/login",
                          json={"email": "user@example.com", "password": "wrongpass1"})
        assert res.status_code == 401

    def test_short_password_rejected(self):
        res = client.post("/api/auth/register",
                          json={"email": "x@example.com", "password": "short"})
        assert res.status_code == 422

    def test_garbage_token(self):
        assert client.get("/api/auth/me",
                          headers={"Authorization": "Bearer not.a.token"}).status_code == 401


class TestOwnership:
    def test_deals_require_auth(self):
        assert client.post("/api/deals", json=DEAL).status_code == 401
        assert client.get("/api/deals").status_code == 401

    def test_users_cannot_see_each_others_deals(self):
        _, alice = signup("alice@example.com")   # admin (first)
        _, bob = signup("bob@example.com")

        deal_id = client.post("/api/deals", json=DEAL, headers=bob).json()["id"]
        _, carol = signup("carol@example.com")
        assert client.get(f"/api/deals/{deal_id}", headers=carol).status_code == 404
        assert client.get("/api/deals", headers=carol).json() == []
        assert client.delete(f"/api/deals/{deal_id}", headers=carol).status_code == 404

        # Owner and admin both see it
        assert client.get(f"/api/deals/{deal_id}", headers=bob).status_code == 200
        assert client.get(f"/api/deals/{deal_id}", headers=alice).status_code == 200

    def test_analysis_stays_public(self):
        assert client.post("/api/analyze", json=DEAL).status_code == 200


class TestCompPermissions:
    COMP = dict(kind="sale", use="residential", region="Dar es Salaam",
                district="Kinondoni", price=400_000_000, area_sqm=320.0,
                observed_date="2026-03", source="test agency")

    def test_contribution_requires_auth_and_is_attributed(self):
        assert client.post("/api/comps", json=self.COMP).status_code == 401
        _, headers = signup("valuer@example.com")
        created = client.post("/api/comps", json=self.COMP, headers=headers).json()
        assert created["contributor"] == "valuer@example.com"

    def test_reads_stay_public(self):
        assert client.get("/api/comps").status_code == 200
        assert client.get("/api/comps/stats").status_code == 200

    def test_only_admin_deletes(self):
        _, admin = signup("admin@example.com")
        _, member = signup("member@example.com")
        created = client.post("/api/comps", json=self.COMP, headers=member).json()
        assert client.delete(f"/api/comps/{created['id']}", headers=member).status_code == 403
        assert client.delete(f"/api/comps/{created['id']}", headers=admin).status_code == 200
