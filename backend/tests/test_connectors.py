"""Connector tests — fully mocked HTTP; no network in the test suite."""

import pytest

from connectors import base, fx, worldbank
from connectors.base import DataPoint, FetchError
from connectors.service import market_snapshot


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "CACHE_PATH", tmp_path / "cache.db")


def wb_body(code_values):
    """Fake World Bank response: list of (year, value)."""
    return [{"page": 1},
            [{"indicator": {"id": "X", "value": "X"}, "date": str(y), "value": v}
             for y, v in code_values]]


FX_BODY = {"result": "success", "time_last_update_utc": "Sun, 05 Jul 2026 00:02:31 +0000",
           "rates": {"TZS": 2621.42, "KES": 129.5}}


class TestWorldBank:
    def test_latest_non_null(self):
        body = wb_body([(2025, None), (2024, 3.1), (2023, 4.8)])
        p = worldbank.get_indicator("inflation_cpi_yoy", "TZA", fetcher=lambda url: body)
        assert p.value == pytest.approx(0.031)
        assert p.as_of == "2024"
        assert p.provenance == "live"

    def test_all_null_returns_none(self):
        body = wb_body([(2025, None), (2024, None)])
        assert worldbank.get_indicator("lending_rate", "TZA", fetcher=lambda url: body) is None

    def test_bad_shape_raises(self):
        with pytest.raises(FetchError):
            worldbank.get_indicator("gdp_growth", "TZA", fetcher=lambda url: {"oops": 1})


class TestFX:
    def test_rate(self):
        p = fx.usd_rate("TZS", fetcher=lambda url: FX_BODY)
        assert p.value == pytest.approx(2621.42)
        assert p.unit == "TZS_per_USD"

    def test_missing_currency(self):
        with pytest.raises(FetchError):
            fx.usd_rate("XXX", fetcher=lambda url: FX_BODY)


class TestCache:
    def point(self):
        return DataPoint("s", 1.0, "fraction", "2025", "src", "url",
                         base.now_iso(), "live")

    def test_roundtrip(self):
        base.cache_put("k", self.point())
        got = base.cache_get("k", max_age_seconds=60)
        assert got.value == 1.0 and got.provenance == "cache" and not got.stale

    def test_expiry_and_stale_fallback(self, monkeypatch):
        base.cache_put("k", self.point())
        real_time = base.time.time
        monkeypatch.setattr(base.time, "time", lambda: real_time() + 7 * 3600)
        assert base.cache_get("k", max_age_seconds=6 * 3600) is None
        fallback = base.cache_get("k", max_age_seconds=None)
        assert fallback is not None and fallback.stale


class TestSnapshot:
    def live_fetcher(self, url):
        if "worldbank" in url:
            return wb_body([(2025, 3.33)])
        return FX_BODY

    def test_live_path(self):
        snap = market_snapshot("tz", fetcher=self.live_fetcher)
        s = snap["series"]
        assert s["inflation_cpi_yoy"]["provenance"] == "live"
        assert s["usd_tzs"]["value"] == pytest.approx(2621.42)
        # Reference-only series always present, marked as such
        assert s["policy_rate"]["provenance"] == "reference"
        assert "verify" in s["policy_rate"]["note"]

    def test_falls_back_to_reference_when_offline(self):
        def dead(url):
            raise FetchError("offline")
        snap = market_snapshot("tz", fetcher=dead)
        s = snap["series"]
        assert s["inflation_cpi_yoy"]["provenance"] == "reference"
        assert s["usd_tzs"]["provenance"] == "reference"
        # lending_rate has no reference entry → reported missing
        assert "lending_rate" in snap["missing"]

    def test_second_call_serves_cache(self):
        calls = {"n": 0}
        def counting(url):
            calls["n"] += 1
            return self.live_fetcher(url)
        market_snapshot("tz", fetcher=counting)
        first = calls["n"]
        snap = market_snapshot("tz", fetcher=counting)
        assert calls["n"] == first  # nothing refetched inside TTL
        assert snap["series"]["inflation_cpi_yoy"]["provenance"] == "cache"

    def test_unknown_jurisdiction(self):
        with pytest.raises(ValueError):
            market_snapshot("zz")
