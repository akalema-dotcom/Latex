"""
app/services/audit_service.py
=============================
Audit log service. Append-only. Every important business & security event
goes through here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        *,
        event: str,
        organization_id: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        actor_agent_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> AuditLog:
        entry = AuditLog(
            organization_id=organization_id,
            event=event,
            actor_user_id=actor_user_id,
            actor_agent_id=actor_agent_id,
            ip_address=ip_address,
            user_agent=user_agent,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            occurred_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_organization(
        self, organization_id: str, event: Optional[str] = None, limit: int = 100,
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.occurred_at.desc())
            .limit(limit)
        )
        if event:
            stmt = stmt.where(AuditLog.event == event)
        return list(self.db.execute(stmt).scalars())
