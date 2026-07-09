import io

import pytest
from fastapi.testclient import TestClient

from app import comps, ingest, store
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")


def admin_headers():
    reg = client.post("/api/auth/register",
                      json={"email": "admin@example.com", "password": "s3cretpass"}).json()
    return {"Authorization": f"Bearer {reg['access_token']}"}


def member_headers():
    client.post("/api/auth/register",
                json={"email": "first@example.com", "password": "s3cretpass"})  # admin
    reg = client.post("/api/auth/register",
                      json={"email": "member@example.com", "password": "s3cretpass"}).json()
    return {"Authorization": f"Bearer {reg['access_token']}"}


ROW = {"kind": "sale", "use": "residential", "region": "Dar es Salaam",
       "district": "Kinondoni", "price": "400000000", "area_sqm": "320",
       "observed_date": "2026-03"}


class TestNormalize:
    def test_valid(self):
        rec, reason = ingest.normalize(ROW, "feed-x")
        assert reason is None
        assert rec["price"] == 400_000_000 and rec["area_sqm"] == 320
        assert rec["contributor"] == "ingest:feed-x"

    def test_strips_thousands_separators(self):
        rec, _ = ingest.normalize({**ROW, "price": "400,000,000"}, "f")
        assert rec["price"] == 400_000_000

    def test_rejects_bad_date(self):
        _, reason = ingest.normalize({**ROW, "observed_date": "March 2026"}, "f")
        assert "observed_date" in reason

    def test_rejects_bad_kind(self):
        _, reason = ingest.normalize({**ROW, "kind": "lease"}, "f")
        assert "kind" in reason

    def test_rejects_missing_price(self):
        _, reason = ingest.normalize({**ROW, "price": ""}, "f")
        assert "price" in reason


class TestIngestCore:
    def test_inserts_and_dedups_within_batch(self):
        rows = [ROW, dict(ROW), {**ROW, "district": "Ilala"}]  # first two identical
        out = ingest.ingest(rows, "feed-a")
        assert out["inserted"] == 2
        assert out["skipped_duplicate"] == 1
        assert len(comps.list_comps({})) == 2

    def test_dedups_against_existing_db(self):
        ingest.ingest([ROW], "feed-a")
        out = ingest.ingest([ROW], "feed-a")  # same content again
        assert out["inserted"] == 0 and out["skipped_duplicate"] == 1

    def test_dry_run_writes_nothing(self):
        out = ingest.ingest([ROW], "feed-a", dry_run=True)
        assert out["inserted"] == 1 and out["preview"]
        assert len(comps.list_comps({})) == 0

    def test_rejections_reported(self):
        out = ingest.ingest([ROW, {**ROW, "price": "-5"}], "feed-a")
        assert out["inserted"] == 1 and out["rejected_count"] == 1
        assert out["rejected"][0]["row"] == 1


class TestCsvAdapter:
    def test_csv_with_matching_headers(self):
        csv_text = ("kind,use,region,district,price,area_sqm,observed_date\n"
                    "sale,residential,Dar es Salaam,Kinondoni,400000000,320,2026-03\n"
                    "sale,residential,Dar es Salaam,Ilala,300000000,250,2026-02\n")
        out = ingest.from_csv(csv_text, "csv-feed")
        assert out["inserted"] == 2

    def test_csv_field_mapping(self):
        csv_text = ("Type,Category,Region,Area,Price(TZS),Size,Date\n"
                    "sale,residential,Dar es Salaam,Kinondoni,400000000,320,2026-03\n")
        out = ingest.from_csv(csv_text, "partner", mapping={
            "kind": "Type", "use": "Category", "region": "Region",
            "district": "Area", "price": "Price(TZS)", "area_sqm": "Size",
            "observed_date": "Date"})
        assert out["inserted"] == 1

    def test_sample_partner_csv_file(self):
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "scripts" / "sample_partner_feed.csv"
        out = ingest.from_csv(path.read_text(), "sample-partner")
        assert out["inserted"] == 6
        assert all("ingest:sample-partner" == c["contributor"] for c in comps.list_comps({}))


class TestApi:
    def test_json_ingest_admin_only(self):
        member = member_headers()
        assert client.post("/api/ingest/json",
                           json={"source": "feed", "records": [ROW]},
                           headers=member).status_code == 403

    def test_json_ingest_flow(self):
        admin = admin_headers()
        # dry run first
        dry = client.post("/api/ingest/json",
                          json={"source": "feed", "records": [ROW], "dry_run": True},
                          headers=admin).json()
        assert dry["inserted"] == 1 and dry["dry_run"] is True
        assert client.get("/api/comps").json() == []
        # commit
        live = client.post("/api/ingest/json",
                           json={"source": "feed", "records": [ROW], "dry_run": False},
                           headers=admin).json()
        assert live["inserted"] == 1
        assert len(client.get("/api/comps").json()) == 1

    def test_json_ingest_with_mapping(self):
        admin = admin_headers()
        out = client.post("/api/ingest/json", json={
            "source": "portal", "dry_run": False,
            "records": [{"t": "sale", "u": "residential", "reg": "Dar es Salaam",
                         "dist": "Kinondoni", "p": 400000000, "a": 320, "d": "2026-03"}],
            "mapping": {"kind": "t", "use": "u", "region": "reg", "district": "dist",
                        "price": "p", "area_sqm": "a", "observed_date": "d"},
        }, headers=admin).json()
        assert out["inserted"] == 1

    def test_csv_upload_endpoint(self):
        admin = admin_headers()
        csv_bytes = ("kind,use,region,district,price,area_sqm,observed_date\n"
                     "sale,residential,Dar es Salaam,Kinondoni,400000000,320,2026-03\n").encode()
        res = client.post("/api/ingest/csv?source=upload&dry_run=false", headers=admin,
                          files={"file": ("feed.csv", io.BytesIO(csv_bytes), "text/csv")})
        assert res.status_code == 200 and res.json()["inserted"] == 1
