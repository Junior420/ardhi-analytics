"""Saved deals — owner-scoped persistence (SQLite locally, Postgres via
DATABASE_URL, e.g. Supabase)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import inspect, text

from dbcore import engine_for

_DATA_DIR = Path(os.environ.get("ARDHI_DATA_DIR",
                                Path(__file__).resolve().parent.parent / "data"))
DB_PATH = _DATA_DIR / "ardhi.db"

_SCHEMA = """CREATE TABLE IF NOT EXISTS deals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    owner_id TEXT NOT NULL DEFAULT ''
)"""


def _engine():
    engine = engine_for(DB_PATH)
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA))
    # Migrate pre-auth databases that lack the owner column.
    cols = [c["name"] for c in inspect(engine).get_columns("deals")]
    if "owner_id" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE deals ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''"))
    return engine


def save_deal(deal: dict, owner_id: str) -> dict:
    deal_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc).isoformat()
    with _engine().begin() as conn:
        conn.execute(text(
            "INSERT INTO deals (id, name, created_at, payload, owner_id) "
            "VALUES (:id, :name, :created, :payload, :owner)"),
            {"id": deal_id, "name": deal.get("name", "Untitled deal"),
             "created": created, "payload": json.dumps(deal), "owner": owner_id})
    return {"id": deal_id, "name": deal.get("name", "Untitled deal"), "created_at": created}


def list_deals(owner_id: Optional[str] = None) -> list[dict]:
    """Deals for one owner; owner_id=None lists all (admin use)."""
    sql = "SELECT id, name, created_at FROM deals"
    params: dict = {}
    if owner_id is not None:
        sql += " WHERE owner_id = :owner"
        params["owner"] = owner_id
    with _engine().connect() as conn:
        rows = conn.execute(text(sql + " ORDER BY created_at DESC"), params).all()
    return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]


def get_deal(deal_id: str) -> Optional[dict]:
    """Returns {"payload": ..., "owner_id": ...} or None."""
    with _engine().connect() as conn:
        row = conn.execute(text(
            "SELECT payload, owner_id FROM deals WHERE id = :id"), {"id": deal_id}).first()
    if row is None:
        return None
    return {"payload": json.loads(row[0]), "owner_id": row[1]}


def delete_deal(deal_id: str) -> bool:
    with _engine().begin() as conn:
        result = conn.execute(text("DELETE FROM deals WHERE id = :id"), {"id": deal_id})
    return result.rowcount > 0
