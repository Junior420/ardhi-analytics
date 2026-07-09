"""AI narrative tests — the Anthropic client is fully mocked, so these run
offline with no API key. They verify wiring, grounding-context assembly, and
graceful degradation, not model output quality."""

import sys
import types

import pytest
from fastapi.testclient import TestClient

from app import narrative
from app.main import app
from app.schemas import DealInput

client = TestClient(app)

DEAL = {
    "name": "Narrative test deal",
    "purchase_price": 450_000_000,
    "gross_rent_annual": 54_000_000,
    "operating_expenses_annual": 12_000_000,
    "hold_years": 7,
    "exit_cap_rate": 0.09,
    "discount_rate": 0.14,
    "loan": {"ltv": 0.6, "annual_rate": 0.15, "term_years": 15},
}


class _FakeBlock:
    type = "text"
    def __init__(self, text): self.text = text


class _FakeMessage:
    model = "claude-opus-4-8"
    def __init__(self, text): self.content = [_FakeBlock(text)]


def _install_fake_anthropic(monkeypatch, capture=None, text="## Executive Summary\nBuy."):
    """Insert a fake `anthropic` module whose client echoes a canned message."""
    mod = types.ModuleType("anthropic")

    class FakeAnthropic:
        def __init__(self, *a, **k):
            self.messages = self

        def create(self, **kwargs):
            if capture is not None:
                capture.update(kwargs)
            return _FakeMessage(text)

    mod.Anthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


class TestAvailability:
    def test_unavailable_without_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert narrative.available() is False

    def test_status_endpoint(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        body = client.get("/api/narrative/status").json()
        assert body["available"] is False
        assert body["model"]

    def test_endpoint_503_when_unconfigured(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert client.post("/api/narrative", json=DEAL).status_code == 503


class TestGeneration:
    def test_generate_returns_markdown(self, monkeypatch):
        _install_fake_anthropic(monkeypatch)
        out = narrative.generate(DealInput(**DEAL))
        assert "Executive Summary" in out["markdown"]
        assert out["model"] == "claude-opus-4-8"
        assert "not legal" in out["disclaimer"].lower()

    def test_context_is_grounded_and_complete(self, monkeypatch):
        capture = {}
        _install_fake_anthropic(monkeypatch, capture=capture)
        narrative.generate(DealInput(**DEAL))
        # The user message carries the computed JSON the model must ground on
        user_content = capture["messages"][0]["content"]
        assert "metrics" in user_content and "monte_carlo" in user_content
        assert "compliance_flags" in user_content
        # System prompt forbids inventing figures
        assert "ONLY the numbers" in capture["system"]
        assert capture["model"] == "claude-opus-4-8"

    def test_endpoint_success(self, monkeypatch):
        _install_fake_anthropic(monkeypatch, text="## Executive Summary\nStrong buy.")
        res = client.post("/api/narrative", json=DEAL)
        assert res.status_code == 200
        assert "Strong buy" in res.json()["markdown"]

    def test_endpoint_502_on_model_error(self, monkeypatch):
        mod = types.ModuleType("anthropic")

        class Boom:
            def __init__(self, *a, **k): self.messages = self
            def create(self, **k): raise RuntimeError("api down")

        mod.Anthropic = Boom
        monkeypatch.setitem(sys.modules, "anthropic", mod)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        assert client.post("/api/narrative", json=DEAL).status_code == 502
