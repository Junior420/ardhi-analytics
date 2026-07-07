"""Saved deals — SQLite persistence, owner-scoped."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(os.environ.get("ARDHI_DATA_DIR",
                                Path(__file__).resolve().parent.parent / "data"))
DB_PATH = _DATA_DIR / "ardhi.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS deals (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload TEXT NOT NULL,
        owner_id TEXT NOT NULL DEFAULT ''
    )""")
    # Migrate pre-auth databases that lack the owner column.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(deals)")]
    if "owner_id" not in cols:
        conn.execute("ALTER TABLE deals ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")
    return conn


def save_deal(deal: dict, owner_id: str) -> dict:
    deal_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute("INSERT INTO deals VALUES (?, ?, ?, ?, ?)",
                     (deal_id, deal.get("name", "Untitled deal"), created,
                      json.dumps(deal), owner_id))
    return {"id": deal_id, "name": deal.get("name", "Untitled deal"), "created_at": created}


def list_deals(owner_id: Optional[str] = None) -> list[dict]:
    """Deals for one owner; owner_id=None lists all (admin use)."""
    sql = "SELECT id, name, created_at FROM deals"
    params: tuple = ()
    if owner_id is not None:
        sql += " WHERE owner_id = ?"
        params = (owner_id,)
    with _conn() as conn:
        rows = conn.execute(sql + " ORDER BY created_at DESC", params).fetchall()
    return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]


def get_deal(deal_id: str) -> Optional[dict]:
    """Returns {"payload": ..., "owner_id": ...} or None."""
    with _conn() as conn:
        row = conn.execute("SELECT payload, owner_id FROM deals WHERE id = ?",
                           (deal_id,)).fetchone()
    if row is None:
        return None
    return {"payload": json.loads(row[0]), "owner_id": row[1]}


def delete_deal(deal_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
    return cur.rowcount > 0
