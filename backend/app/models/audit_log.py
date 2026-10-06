"""
app/models/audit_log.py
=======================
Immutable audit log for every important business & security event.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, JSON, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin


# Canonical event types — kept here so code & migrations reference the same names.
AUDIT_EVENTS: tuple[str, ...] = (
    # Auth
    "USER_REGISTERED", "USER_LOGIN", "USER_LOGOUT", "PASSWORD_CHANGED",
    "PASSWORD_RESET", "EMAIL_VERIFIED", "SESSION_REVOKED",
    # Orders / inventory
    "ORDER_CREATED", "ORDER_UPDATED", "ORDER_CANCELLED",
    "INVENTORY_CHANGED", "PURCHASE_ORDER_CREATED",
    # Finance
    "EXPENSE_CREATED", "TRANSACTION_RECORDED",
    # Currency
    "CURRENCY_RATE_UPDATED", "CURRENCY_CONVERSION_PERFORMED",
    # AI
    "AI_ACTION_STARTED", "AI_ACTION_COMPLETED", "AI_ACTION_FAILED",
    "AI_APPROVAL_REQUESTED", "AI_APPROVAL_APPROVED", "AI_APPROVAL_REJECTED",
    # Approvals (general)
    "APPROVAL_REQUESTED", "APPROVAL_APPROVED", "APPROVAL_REJECTED",
    # Org / settings
    "ORGANIZATION_CREATED", "ORGANIZATION_UPDATED", "SETTINGS_UPDATED",
    # Channels
    "MESSAGE_RECEIVED", "MESSAGE_SENT",
)


class AuditLog(Base, UUIDPkMixin, TimestampMixin):
    """
    Audit log entry.

    organization_id is NULLABLE because some events (USER_REGISTERED,
    PASSWORD_RESET, EMAIL_VERIFIED) occur before the user belongs to an
    organization.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_org_event", "organization_id", "event"),)

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True,
    )

    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    actor_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_agents.id"), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
