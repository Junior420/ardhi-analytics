"""Test DB isolation.

Default: tests run on per-test SQLite files (DATABASE_URL is cleared so a
developer's environment can't leak in). Set ARDHI_TEST_DATABASE_URL to run
the whole suite against a real PostgreSQL server instead — tables are
dropped before each test so every test still starts clean.
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import text

import dbcore

_PG_URL = os.environ.get("ARDHI_TEST_DATABASE_URL")


@pytest.fixture(autouse=True)
def _db_isolation(monkeypatch):
    if _PG_URL:
        monkeypatch.setenv("DATABASE_URL", _PG_URL)
        engine = dbcore.engine_for(Path("/unused"))
        with engine.begin() as conn:
            for table in ("deals", "users", "comparables", "market_cache"):
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
