"""Connector primitives: provenance-stamped data points, HTTP fetch, cache."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

CACHE_PATH = Path(os.environ.get("ARDHI_DATA_DIR",
                                 Path(__file__).resolve().parent.parent / "data")) / "market_cache.db"
DEFAULT_TTL_SECONDS = 6 * 3600


class FetchError(Exception):
    pass


@dataclass(frozen=True)
class DataPoint:
    series: str            # e.g. "inflation_cpi_yoy"
    value: float
    unit: str              # "percent", "TZS_per_USD", ...
    as_of: str             # period the value describes (e.g. "2025", a date)
    source: str            # human-readable source name
    source_url: str
    retrieved_at: str      # ISO timestamp of retrieval
    provenance: str        # "live" | "cache" | "reference"
    stale: bool = False
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def fetch_json(url: str, timeout: float = 15.0) -> dict | list:
    """GET a JSON document. Raises FetchError on any failure."""
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:  # network, HTTP status, or JSON decode
        raise FetchError(f"fetch failed for {url}: {e}") from e


def _conn() -> sqlite3.Connection:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        stored_at REAL NOT NULL
    )""")
    return conn


def cache_put(key: str, point: DataPoint) -> None:
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
                     (key, json.dumps(point.to_dict()), time.time()))


def cache_get(key: str, max_age_seconds: Optional[float] = None) -> Optional[DataPoint]:
    """Return the cached point, or None. With max_age_seconds=None any age is
    accepted (used for degraded fallback); the point is flagged stale if it
    exceeds the default TTL."""
    with _conn() as conn:
        row = conn.execute("SELECT payload, stored_at FROM cache WHERE key = ?",
                           (key,)).fetchone()
    if row is None:
        return None
    payload, stored_at = json.loads(row[0]), row[1]
    age = time.time() - stored_at
    if max_age_seconds is not None and age > max_age_seconds:
        return None
    payload["provenance"] = "cache"
    payload["stale"] = age > DEFAULT_TTL_SECONDS
    return DataPoint(**payload)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
