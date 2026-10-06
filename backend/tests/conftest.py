"""
tests/conftest.py
=================
Pytest fixtures shared across all test modules.

Provides:
- a fresh in-memory SQLite DB per test
- a TestClient with seeded roles + currencies
- helper factories for users / organizations / auth tokens
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator

# Make the project importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force a clean test environment
os.environ.pop("DATABASE_URL", None)
os.environ.pop("SECRET_KEY", None)
os.environ.pop("JWT_SECRET_KEY", None)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-must-be-at-least-32-characters-long-xx"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-must-be-at-least-32-characters"
os.environ["APP_ENV"] = "testing"
os.environ["EMAIL_PROVIDER"] = "noop"
os.environ["EXCHANGE_RATE_PROVIDER"] = "mock"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.user import User, Role, UserRole
from app.services.auth_service import _seed_default_roles
from app.api.v1.endpoints.currencies import _ensure_currencies_seeded


@pytest.fixture(scope="function")
def db_session() -> Iterator[Session]:
    """Fresh DB session per test."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        _seed_default_roles(db)
        _ensure_currencies_seeded(db)
        db.commit()
        yield db
        db.rollback()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Iterator[TestClient]:
    """TestClient with a fresh DB."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def registered_user(client: TestClient, db_session: Session) -> dict:
    """A registered + verified user with their auth tokens."""
    email = "tester@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "Sup3rSecret!", "full_name": "Tester",
    })
    # Auto-verify (we're using noop email)
    user = db_session.execute(select(User).where(User.email == email)).scalar_one()
    user.email_verified = True
    db_session.commit()

    r = client.post("/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"})
    tokens = r.json()
    return {
        "user": user,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


@pytest.fixture
def owner_user(client: TestClient, db_session: Session) -> dict:
    """A registered + verified user with OWNER role + organization."""
    email = "owner@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "Sup3rSecret!", "full_name": "Owner",
    })
    user = db_session.execute(select(User).where(User.email == email)).scalar_one()
    user.email_verified = True
    db_session.commit()

    r = client.post("/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"})
    tokens = r.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Create org
    r = client.post("/api/v1/organizations", json={
        "name": "Test Org", "slug": "test-org",
        "country_code": "UG", "base_currency": "UGX",
        "locale": "en-UG", "timezone": "Africa/Kampala",
        "tax_rate_pct": 18,
    }, headers=headers)
    org_id = r.json()["id"]

    # Promote to OWNER
    owner_role = db_session.execute(select(Role).where(Role.name == "OWNER")).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=owner_role.id, role_name="OWNER"))
    db_session.commit()

    # Refresh token (to include new role + permissions)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    tokens = r.json()
    return {
        "user": user,
        "org_id": org_id,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }
