"""Password hashing (bcrypt) and JWT access tokens (PyJWT).

Kept deliberately small and dependency-light: bcrypt directly (no passlib,
which has known bcrypt-version breakage) and PyJWT for stateless tokens.
"""
from __future__ import annotations

from datetime import datetime, timedelta, UTC

import bcrypt
import jwt

from app.config import get_settings

# bcrypt truncates input at 72 bytes; guard so long passwords don't silently
# lose entropy or raise.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:_BCRYPT_MAX_BYTES],
            hashed.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, extra: dict | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    """Return the token payload, or None if invalid/expired."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
