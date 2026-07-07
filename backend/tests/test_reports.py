"""Template dispatch tests. PDF titles are stored uncompressed in metadata,
so template identity is asserted via the /Title entry in the raw bytes."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

DEAL = {
    "name": "Template test deal",
    "purchase_price": 450_000_000,
    "gross_rent_annual": 54_000_000,
    "vacancy_rate": 0.07,
    "operating_expenses_annual": 12_000_000,
    "rent_growth": 0.06,
    "expense_growth": 0.05,
    "hold_years": 7,
    "exit_cap_rate": 0.09,
    "discount_rate": 0.14,
    "loan": {"ltv": 0.6, "annual_rate": 0.15, "term_years": 15},
}


def get_pdf(template=None):
    url = "/api/report" + (f"?template={template}" if template else "")
    res = client.post(url, json=DEAL)
    assert res.status_code == 200, res.text
    assert res.content[:5] == b"%PDF-"
    return res


class TestTemplates:
    def test_default_is_investor(self):
        res = get_pdf()
        assert b"Investment Appraisal" in res.content
        assert "_investor.pdf" in res.headers["content-disposition"]

    def test_bank_template(self):
        res = get_pdf("bank")
        assert b"Collateral Assessment" in res.content

    def test_valuer_template(self):
        res = get_pdf("valuer")
        assert b"Valuation Workpaper" in res.content

    def test_templates_differ(self):
        contents = {t: get_pdf(t).content for t in ("investor", "bank", "valuer")}
        assert len({len(c) for c in contents.values()}) == 3 or \
            len(set(contents.values())) == 3

    def test_unknown_template_rejected(self):
        res = client.post("/api/report?template=fancy", json=DEAL)
        assert res.status_code == 422
        assert "unknown template" in res.json()["detail"]

    def test_bank_without_loan_still_renders(self):
        deal = {k: v for k, v in DEAL.items() if k != "loan"}
        res = client.post("/api/report?template=bank", json=deal)
        assert res.status_code == 200
        assert res.content[:5] == b"%PDF-"

    def test_valuer_without_loan(self):
        deal = {k: v for k, v in DEAL.items() if k != "loan"}
        res = client.post("/api/report?template=valuer", json=deal)
        assert res.status_code == 200
