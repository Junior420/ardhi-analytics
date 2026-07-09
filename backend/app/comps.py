"""Comparables database: contributed sale/rent observations + market stats.

The long-term moat: real transaction evidence. Every record carries its
source and contributor. Statistics are unit-price based (per m²) and come
with dispersion-aware confidence grades so thin evidence is never presented
as strong.
"""

from __future__ import annotations

import hashlib
import statistics
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import inspect, text

from dbcore import engine_for

from . import store

_SCHEMA = """CREATE TABLE IF NOT EXISTS comparables (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('sale', 'rent')),
    use TEXT NOT NULL CHECK (use IN ('residential', 'commercial', 'land')),
    region TEXT NOT NULL,
    district TEXT NOT NULL,
    price REAL NOT NULL CHECK (price > 0),
    currency TEXT NOT NULL DEFAULT 'TZS',
    area_sqm REAL CHECK (area_sqm IS NULL OR area_sqm > 0),
    observed_date TEXT NOT NULL,
    source TEXT NOT NULL,
    contributor TEXT NOT NULL DEFAULT 'anonymous',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    dedup_hash TEXT
)"""


def _engine():
    engine = engine_for(store.DB_PATH)
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA))
    # Migrate pre-ingestion databases that lack the dedup column.
    cols = [c["name"] for c in inspect(engine).get_columns("comparables")]
    if "dedup_hash" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE comparables ADD COLUMN dedup_hash TEXT"))
    return engine


def dedup_hash(rec: dict) -> str:
    """Content fingerprint used to skip duplicate observations. Two records
    for the same transaction (same segment, price, area, date, source) hash
    equal even if ingested twice or from overlapping feeds."""
    parts = [str(rec.get("kind", "")).lower(), str(rec.get("use", "")).lower(),
             str(rec.get("region", "")).strip().lower(),
             str(rec.get("district", "")).strip().lower(),
             str(round(float(rec["price"]))),
             str(round(float(rec["area_sqm"]))) if rec.get("area_sqm") else "",
             str(rec.get("observed_date", "")),
             str(rec.get("source", "")).strip().lower()]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def hash_exists(h: str) -> bool:
    with _engine().connect() as conn:
        row = conn.execute(text("SELECT 1 FROM comparables WHERE dedup_hash = :h LIMIT 1"),
                           {"h": h}).first()
    return row is not None


def add_comp(rec: dict) -> dict:
    rec = dict(rec)
    rec["id"] = str(uuid.uuid4())
    rec["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rec.setdefault("dedup_hash", dedup_hash(rec))
    with _engine().begin() as conn:
        conn.execute(text(
            """INSERT INTO comparables
               (id, kind, use, region, district, price, currency, area_sqm,
                observed_date, source, contributor, notes, created_at, dedup_hash)
               VALUES (:id, :kind, :use, :region, :district, :price, :currency,
                       :area_sqm, :observed_date, :source, :contributor, :notes,
                       :created_at, :dedup_hash)"""), rec)
    return rec


def _where(filters: dict) -> tuple[str, dict]:
    clauses, params = [], {}
    for field in ("kind", "use", "region", "district"):
        if filters.get(field):
            # region/district match case-insensitively; kind/use are enums
            clauses.append(f"LOWER({field}) = LOWER(:{field})")
            params[field] = filters[field]
    if filters.get("since"):
        clauses.append("observed_date >= :since")
        params["since"] = filters["since"]
    sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return sql, params


def list_comps(filters: dict, limit: int = 100) -> list[dict]:
    sql, params = _where(filters)
    params["_limit"] = min(limit, 500)
    with _engine().connect() as conn:
        rows = conn.execute(text(
            f"SELECT * FROM comparables{sql} ORDER BY observed_date DESC LIMIT :_limit"),
            params).mappings().all()
    return [dict(r) for r in rows]


def delete_comp(comp_id: str) -> bool:
    with _engine().begin() as conn:
        result = conn.execute(text("DELETE FROM comparables WHERE id = :id"), {"id": comp_id})
    return result.rowcount > 0


def _confidence(n: int, rel_dispersion: Optional[float], spread: Optional[float]) -> str:
    """Evidence quality. rel_dispersion (MAD/median) is robust to outliers,
    so the max/min spread is checked separately — one wild comp should still
    lower trust in the evidence set."""
    if n < 3 or rel_dispersion is None:
        return "low"
    if n >= 5 and rel_dispersion <= 0.15:
        grade = "high"
    elif rel_dispersion <= 0.30:
        grade = "medium"
    else:
        return "low"
    if spread is not None and spread > 2.0:
        grade = "medium" if grade == "high" else "low"
    return grade


def stats(filters: dict) -> dict:
    """Unit-price statistics (per m²) over matching comps that have an area."""
    comps = list_comps(filters, limit=500)
    unit_prices = [c["price"] / c["area_sqm"] for c in comps if c["area_sqm"]]
    out = {"count": len(comps), "count_with_area": len(unit_prices), "filters": filters}
    if not unit_prices:
        out.update({"confidence": "low",
                    "note": "No comparables with area data match these filters."})
        return out
    median = statistics.median(unit_prices)
    mad = statistics.median(abs(p - median) for p in unit_prices)
    rel = mad / median if median else None
    out.update({
        "unit_price_median": median,
        "unit_price_mean": statistics.fmean(unit_prices),
        "unit_price_min": min(unit_prices),
        "unit_price_max": max(unit_prices),
        "relative_dispersion": rel,
        "date_range": [min(c["observed_date"] for c in comps),
                       max(c["observed_date"] for c in comps)],
        "confidence": _confidence(len(unit_prices), rel,
                                  max(unit_prices) / min(unit_prices)),
    })
    return out


def indicate_value(area_sqm: float, filters: dict) -> dict:
    """Evidence-based value indication: median unit price × subject area.
    A screening tool, not a valuation — heavily caveated by confidence."""
    if area_sqm <= 0:
        raise ValueError("area_sqm must be positive")
    s = stats(filters)
    if "unit_price_median" not in s:
        return {"indicated_value": None, "stats": s,
                "note": "Insufficient comparable evidence for an indication."}
    return {
        "indicated_value": s["unit_price_median"] * area_sqm,
        "indicated_range": [s["unit_price_min"] * area_sqm, s["unit_price_max"] * area_sqm],
        "area_sqm": area_sqm,
        "stats": s,
        "note": ("Screening indication only (median unit price x area); "
                 "confidence: " + s["confidence"] + ". Not a valuation."),
    }
