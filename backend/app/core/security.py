"""
app/core/security.py
====================
Password hashing, JWT creation/verification, token rotation helpers.

Never store plaintext passwords. Never expose secrets in API responses.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# --- Password hashing (bcrypt directly) -------------------------------------
# passlib+bcrypt4.x has a known incompatibility — we use bcrypt directly.


def hash_password(plain: str) -> str:
    """Hash a password using bcrypt. Truncates to 72 bytes (bcrypt limit)."""
    pw_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        pw_bytes = plain.encode("utf-8")[:72]
        hash_bytes = hashed.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False


# --- JWT --------------------------------------------------------------------
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_EMAIL_VERIFY = "email_verify"
TOKEN_TYPE_PASSWORD_RESET = "password_reset"


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "type": token_type,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(
    user_id: str,
    organization_id: Optional[str] = None,
    roles: Optional[list[str]] = None,
    scopes: Optional[list[str]] = None,
) -> str:
    """Short-lived access token (default 30 minutes)."""
    return _create_token(
        subject=user_id,
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={
            "org": organization_id,
            "roles": roles or [],
            "scopes": scopes or [],
        },
    )


def create_refresh_token(user_id: str, session_id: str) -> str:
    """Longer-lived refresh token, tied to a session."""
    return _create_token(
        subject=user_id,
        token_type=TOKEN_TYPE_REFRESH,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        extra_claims={"sid": session_id},
    )


def create_email_verification_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=TOKEN_TYPE_EMAIL_VERIFY,
        expires_delta=timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
    )


def create_password_reset_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=TOKEN_TYPE_PASSWORD_RESET,
        expires_delta=timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode a JWT. Returns None if invalid / expired."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def decode_token_of_type(token: str, expected_type: str) -> Optional[Dict[str, Any]]:
    """Decode a JWT and verify its type."""
    payload = decode_token(token)
    if not payload or payload.get("type") != expected_type:
        return None
    return payload
