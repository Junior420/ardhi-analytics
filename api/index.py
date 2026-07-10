"""Vercel serverless entrypoint.

Vercel's Python runtime serves the ASGI `app` exported here; vercel.json
rewrites every route to this function. When the repo's backend/ tree is
present (running from a full checkout) it is imported directly; in the
slim Vercel deployment (this file + requirements only) the pinned commit's
backend/ is fetched once per instance from the public GitHub tarball and
cached in /tmp.
"""

import io
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO = "Junior420/ardhi-analytics"
COMMIT = "0d2cce723a14df29b0e6330e574e5c33aa3978f6"  # backend source pin


def _source_root() -> Path:
    local = Path(__file__).resolve().parent.parent / "backend"
    if local.exists():
        return local
    dest = Path("/tmp") / f"ardhi-src-{COMMIT[:12]}"
    marker = dest / ".complete"
    if not marker.exists():
        url = f"https://codeload.github.com/{REPO}/tar.gz/{COMMIT}"
        data = urllib.request.urlopen(url, timeout=30).read()
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            root = tf.getnames()[0].split("/")[0]
            members = [m for m in tf.getmembers()
                       if m.name.startswith(f"{root}/backend/")]
            tf.extractall(dest, members=members)
        (dest / "tarball-root.txt").write_text(root)
        marker.touch()
    root = (dest / "tarball-root.txt").read_text().strip()
    return dest / root / "backend"


sys.path.insert(0, str(_source_root()))

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
