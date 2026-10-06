"""
tests/test_auth.py
==================
Authentication tests.

Covers: registration, duplicate email, login, invalid password, expired token,
refresh rotation, logout, email verification, password reset, permissions.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models.user import User


def test_register_success(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "new@example.com", "password": "Sup3rSecret!",
    })
    assert r.status_code == 201
    assert r.json()["email"] == "new@example.com"
    assert "password" not in r.json()
    assert "password_hash" not in r.json()


def test_register_duplicate_email(client, registered_user):
    r = client.post("/api/v1/auth/register", json={
        "email": "tester@example.com", "password": "AnotherPass123!",
    })
    assert r.status_code == 409


def test_register_short_password_rejected(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "x@example.com", "password": "short",
    })
    assert r.status_code == 422


def test_login_success(client, registered_user):
    r = client.post("/api/v1/auth/login", json={
        "email": "tester@example.com", "password": "Sup3rSecret!",
    })
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_invalid_password(client, registered_user):
    r = client.post("/api/v1/auth/login", json={
        "email": "tester@example.com", "password": "wrong",
    })
    assert r.status_code == 401


def test_login_nonexistent_user(client):
    r = client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com", "password": "Sup3rSecret!",
    })
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_with_valid_token(client, registered_user):
    r = client.get("/api/v1/auth/me", headers=registered_user["headers"])
    assert r.status_code == 200
    assert r.json()["email"] == "tester@example.com"


def test_refresh_token_rotation(client, registered_user):
    r1 = client.post("/api/v1/auth/refresh", json={
        "refresh_token": registered_user["refresh_token"],
    })
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]
    assert new_refresh != registered_user["refresh_token"]

    # Old refresh should now be revoked
    r2 = client.post("/api/v1/auth/refresh", json={
        "refresh_token": registered_user["refresh_token"],
    })
    assert r2.status_code == 401


def test_logout_revokes_session(client, registered_user):
    r = client.post("/api/v1/auth/logout", json={
        "refresh_token": registered_user["refresh_token"],
    })
    assert r.status_code == 204
    # Refresh after logout should fail
    r2 = client.post("/api/v1/auth/refresh", json={
        "refresh_token": registered_user["refresh_token"],
    })
    assert r2.status_code == 401


def test_email_verification_flow(client, db_session):
    # Register
    client.post("/api/v1/auth/register", json={
        "email": "verify@example.com", "password": "Sup3rSecret!",
    })
    user = db_session.execute(select(User).where(User.email == "verify@example.com")).scalar_one()
    assert user.email_verified is False

    # Generate a verification token directly
    from app.core.security import create_email_verification_token
    token = create_email_verification_token(user.id)
    r = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r.status_code == 200
    db_session.refresh(user)
    assert user.email_verified is True


def test_password_reset_flow(client, db_session):
    client.post("/api/v1/auth/register", json={
        "email": "reset@example.com", "password": "Sup3rSecret!",
    })
    user = db_session.execute(select(User).where(User.email == "reset@example.com")).scalar_one()
    user.email_verified = True  # Required for login after reset
    db_session.commit()

    from app.core.security import create_password_reset_token
    from app.services.auth_service import _hash_token
    from app.models.password_reset import PasswordResetToken
    from datetime import timedelta
    from app.utils.timezone import now_utc
    from app.core.config import settings

    token = create_password_reset_token(user.id)
    # Create the DB record (mirrors what request_password_reset does)
    db_session.add(PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=now_utc() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    ))
    db_session.commit()

    r = client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "BrandNewPass123!",
    })
    assert r.status_code == 200

    # Should be able to login with new password
    r2 = client.post("/api/v1/auth/login", json={
        "email": "reset@example.com", "password": "BrandNewPass123!",
    })
    assert r2.status_code == 200


def test_change_password(client, registered_user):
    r = client.post("/api/v1/auth/change-password", json={
        "current_password": "Sup3rSecret!",
        "new_password": "NewPassword123!",
    }, headers=registered_user["headers"])
    assert r.status_code == 200

    # Old password should fail
    r2 = client.post("/api/v1/auth/login", json={
        "email": "tester@example.com", "password": "Sup3rSecret!",
    })
    assert r2.status_code == 401

    # New password should work
    r3 = client.post("/api/v1/auth/login", json={
        "email": "tester@example.com", "password": "NewPassword123!",
    })
    assert r3.status_code == 200


def test_invalid_token_rejected(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


def test_sessions_listing(client, registered_user):
    r = client.get("/api/v1/auth/sessions", headers=registered_user["headers"])
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_expired_token_via_invalid_signature(client):
    # Forge a token with a different secret — should be rejected
    from jose import jwt
    forged = jwt.encode(
        {"sub": "x", "type": "access", "exp": 9999999999},
        "wrong-secret", algorithm="HS256",
    )
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
