"""Vercel serverless entrypoint.

Vercel's Python runtime serves the ASGI `app` exported here; vercel.json
rewrites every route to this function. The backend/ package layout is kept,
so this file only wires up paths and serverless-safe defaults.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

# Only /tmp is writable on Vercel. Used for the SQLite fallback and market
# cache when DATABASE_URL (Supabase/Postgres) isn't configured — note SQLite
# there is per-instance and ephemeral, fine for demo, not for real accounts.
if not os.environ.get("DATABASE_URL"):
    os.environ.setdefault("ARDHI_DATA_DIR", "/tmp/ardhi-data")

# Optional deployment-local secret (never committed): api/_secret.txt holding
# a hex JWT secret. An ARDHI_JWT_SECRET env var set in the Vercel dashboard
# wins; with neither, auth.py falls back to a per-instance random secret,
# which breaks token continuity across serverless cold starts.
_secret_file = Path(__file__).with_name("_secret.txt")
if _secret_file.exists():
    os.environ.setdefault("ARDHI_JWT_SECRET", _secret_file.read_text().strip())

from app.main import app  # noqa: E402,F401
