"""
app/utils/timezone.py
=====================
Timezone helpers.

SQLite returns NAIVE datetimes even when the column is declared
``DateTime(timezone=True)``. PostgreSQL returns AWARE datetimes. To keep
our service code portable across both, every datetime that comes back from
the DB should be passed through ``ensure_aware()`` before being compared.
"""
from __future__ import annotations

from datetime import datetime, timezone


def ensure_aware(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is timezone-aware (assume UTC if naive)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def now_utc() -> datetime:
    """Timezone-aware 'now' in UTC."""
    return datetime.now(timezone.utc)


def is_past(dt: datetime | None) -> bool:
    """True if ``dt`` is in the past (or None)."""
    if dt is None:
        return True
    return now_utc() >= ensure_aware(dt)


def is_future(dt: datetime | None) -> bool:
    """True if ``dt`` is in the future."""
    if dt is None:
        return False
    return now_utc() < ensure_aware(dt)
