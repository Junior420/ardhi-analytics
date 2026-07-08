"""Authentication: email+password accounts, PBKDF2 hashing, JWT sessions.

Single-tenant Phase 1 model: the first registered user becomes admin;
everyone else is a member. Deals are owner-scoped; comp contributions are
attributed to the signed-in user.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from dbcore import engine_for

from . import store

JWT_SECRET = os.environ.get("ARDHI_JWT_SECRET", "")
if not JWT_SECRET:
    # Dev fallback: random per-process secret. Tokens die on restart, which is
    # safe-by-default; set ARDHI_JWT_SECRET in production.
    JWT_SECRET = secrets.token_hex(32)

TOKEN_TTL_HOURS = 24
_PBKDF2_ITERATIONS = 200_000

_bearer = HTTPBearer(auto_error=False)


_SCHEMA = """CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    created_at TEXT NOT NULL
)"""


def _engine():
    engine = engine_for(store.DB_PATH)
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA))
    return engine


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                               _PBKDF2_ITERATIONS).hex()


def register(email: str, password: str) -> dict:
    email = email.strip().lower()
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    salt = secrets.token_hex(16)
    engine = _engine()
    with engine.connect() as conn:
        first_user = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 0
    role = "admin" if first_user else "member"
    user_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (id, email, password_hash, salt, role, created_at) "
                "VALUES (:id, :email, :hash, :salt, :role, :created)"),
                {"id": user_id, "email": email, "hash": _hash(password, salt),
                 "salt": salt, "role": role,
                 "created": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    except IntegrityError:
        raise ValueError("an account with this email already exists")
    return {"id": user_id, "email": email, "role": role}


def authenticate(email: str, password: str) -> Optional[dict]:
    with _engine().connect() as conn:
        row = conn.execute(text("SELECT * FROM users WHERE email = :email"),
                           {"email": email.strip().lower()}).mappings().first()
    if row is None:
        return None
    if not secrets.compare_digest(_hash(password, row["salt"]), row["password_hash"]):
        return None
    return {"id": row["id"], "email": row["email"], "role": row["role"]}


def create_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"invalid or expired token: {e}")


def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> dict:
    """FastAPI dependency: require a valid bearer token."""
    if creds is None:
        raise HTTPException(status_code=401, detail="authentication required")
    claims = decode_token(creds.credentials)
    return {"id": claims["sub"], "email": claims["email"], "role": claims["role"]}
