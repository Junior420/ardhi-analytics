"""Database engine selection, shared by app/ and connectors/.

Set DATABASE_URL (e.g. a Supabase PostgreSQL connection string) to use
Postgres; otherwise a local SQLite file is used. Engines are cached per URL,
so tests that point at fresh SQLite paths each get their own engine.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_engines: dict[str, Engine] = {}


def _normalize(url: str) -> str:
    """Supabase/Heroku hand out postgres:// URLs; SQLAlchemy 2 with the
    psycopg 3 driver wants postgresql+psycopg://."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def engine_for(sqlite_path: Path | str) -> Engine:
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        url = _normalize(env_url)
        # pool_pre_ping drops connections killed by the pooler; pool_recycle
        # avoids Supabase's idle-connection timeout. prepare_threshold=None
        # disables psycopg's prepared statements, which pgbouncer in the
        # Supabase transaction pooler rejects ("prepared statement already
        # exists") — safe for every Supabase connection mode.
        kwargs = {
            "pool_pre_ping": True,
            "pool_recycle": 1800,
            "connect_args": {"prepare_threshold": None},
        }
    else:
        sqlite_path = Path(sqlite_path)
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{sqlite_path}"
        kwargs = {"connect_args": {"check_same_thread": False}}
    engine = _engines.get(url)
    if engine is None:
        engine = _engines[url] = create_engine(url, **kwargs)
    return engine
