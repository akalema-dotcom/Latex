"""
app/api/v1/endpoints/audit_logs.py
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    event: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    if not user.organization_id:
        return []
    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == user.organization_id)
        .order_by(AuditLog.occurred_at.desc())
        .limit(limit)
    )
    if event:
        stmt = stmt.where(AuditLog.event == event)
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "id": r.id,
            "event": r.event,
            "actor_user_id": r.actor_user_id,
            "actor_agent_id": r.actor_agent_id,
            "ip_address": r.ip_address,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "details": r.details,
            "occurred_at": r.occurred_at,
        }
        for r in rows
    ]
