"""Saved deals — SQLite persistence (single-user Phase 1; auth comes later)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ardhi.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS deals (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload TEXT NOT NULL
    )""")
    return conn


def save_deal(deal: dict) -> dict:
    deal_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute("INSERT INTO deals VALUES (?, ?, ?, ?)",
                     (deal_id, deal.get("name", "Untitled deal"), created, json.dumps(deal)))
    return {"id": deal_id, "name": deal.get("name", "Untitled deal"), "created_at": created}


def list_deals() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at FROM deals ORDER BY created_at DESC").fetchall()
    return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]


def get_deal(deal_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT payload FROM deals WHERE id = ?", (deal_id,)).fetchone()
    return json.loads(row[0]) if row else None


def delete_deal(deal_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
    return cur.rowcount > 0
