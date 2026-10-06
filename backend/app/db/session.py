"""
app/db/session.py
=================
Database engine, session factory, FastAPI dependency.

Supports PostgreSQL (production) and SQLite (development) via the
``DATABASE_URL`` environment variable.
"""
from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _engine_kwargs() -> dict:
    url = settings.DATABASE_URL
    kwargs: dict = {
        "pool_pre_ping": True,
        "future": True,
    }
    if url.startswith("sqlite"):
        # SQLite needs check_same_thread=False for FastAPI threads.
        # For in-memory SQLite (:memory:), we MUST use StaticPool so every
        # thread sees the same in-memory DB instance.
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            from sqlalchemy.pool import StaticPool
            kwargs["poolclass"] = StaticPool
    else:
        # PostgreSQL production pool sizing
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_recycle"] = 1800
    return kwargs


engine: Engine = create_engine(settings.DATABASE_URL, **_engine_kwargs())


# Enable SQLite foreign-key enforcement (off by default).
@event.listens_for(Engine, "connect")
def _set_sqlite_fk(dbapi_conn, _):
    if settings.DATABASE_URL.startswith("sqlite"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
