"""Market snapshot service: live -> cache -> reference resolution per series."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

import yaml

from . import fx, worldbank
from .base import (
    DEFAULT_TTL_SECONDS, DataPoint, cache_get, cache_put, fetch_json, now_iso,
)

REFERENCE_PATH = Path(__file__).resolve().parent / "reference_data.yaml"

JURISDICTIONS = {
    "tz": {"iso3": "TZA", "currency": "TZS"},
}


@lru_cache(maxsize=None)
def _reference() -> dict:
    with open(REFERENCE_PATH) as f:
        return yaml.safe_load(f)


def _reference_point(jurisdiction: str, series: str) -> Optional[DataPoint]:
    entry = _reference().get(jurisdiction, {}).get(series)
    if entry is None:
        return None
    return DataPoint(
        series=series, value=float(entry["value"]), unit=entry["unit"],
        as_of=str(entry["as_of"]), source=entry["source"],
        source_url=entry["source_url"], retrieved_at=now_iso(),
        provenance="reference", stale=False,
        note=entry.get("note", "") + " [draft reference data — verify]",
    )


def _resolve(key: str, live: Callable[[], Optional[DataPoint]],
             jurisdiction: str, series: str) -> Optional[DataPoint]:
    """live API -> fresh cache is implicit in live path; on failure use any-age
    cache (flagged stale beyond TTL), then curated reference."""
    cached = cache_get(key, max_age_seconds=DEFAULT_TTL_SECONDS)
    if cached is not None:
        return cached
    try:
        point = live()
        if point is not None:
            cache_put(key, point)
            return point
    except Exception:
        pass
    fallback = cache_get(key, max_age_seconds=None)
    if fallback is not None:
        return fallback
    return _reference_point(jurisdiction, series)


def market_snapshot(jurisdiction: str = "tz",
                    fetcher: Callable = fetch_json) -> dict:
    """All market series for a jurisdiction, each with provenance."""
    if jurisdiction not in JURISDICTIONS:
        raise ValueError(f"no market data mapping for jurisdiction {jurisdiction}")
    cfg = JURISDICTIONS[jurisdiction]
    iso3, currency = cfg["iso3"], cfg["currency"]

    points: dict[str, Optional[DataPoint]] = {}
    for series in ("inflation_cpi_yoy", "gdp_growth", "lending_rate"):
        points[series] = _resolve(
            f"{jurisdiction}:{series}",
            lambda s=series: worldbank.get_indicator(s, iso3, fetcher),
            jurisdiction, series)

    points[f"usd_{currency.lower()}"] = _resolve(
        f"{jurisdiction}:usd_{currency.lower()}",
        lambda: fx.usd_rate(currency, fetcher),
        jurisdiction, f"usd_{currency.lower()}")

    # Reference-only series (no public API).
    for series in ("policy_rate", "mortgage_rate_typical"):
        points[series] = _reference_point(jurisdiction, series)

    return {
        "jurisdiction": jurisdiction,
        "currency": currency,
        "generated_at": now_iso(),
        "series": {k: v.to_dict() for k, v in points.items() if v is not None},
        "missing": [k for k, v in points.items() if v is None],
    }
