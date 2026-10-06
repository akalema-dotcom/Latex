"""
app/models/ai_agent.py
======================
AI agent framework: agents, tasks, actions, approvals.

The AI layer NEVER directly manipulates database tables. It uses tools that
themselves call services. Every action is logged + (if sensitive) requires
human approval.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Integer, ForeignKey, DateTime, JSON, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin


AGENT_STATUS = ("ACTIVE", "PAUSED", "DISABLED")
TASK_STATUS = ("PENDING", "RUNNING", "AWAITING_APPROVAL", "COMPLETED", "FAILED", "CANCELLED")
ACTION_STATUS = ("STARTED", "SUCCESS", "FAILED", "DENIED")


class AIAgent(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    """A named, scoped AI agent attached to an organization."""

    __tablename__ = "ai_agents"
    __table_args__ = (Index("ix_ai_agents_org", "organization_id", "name"),)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="general")
    # e.g. ["orders.create", "inventory.update"]
    permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")

    requires_approval_for: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    api_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    tasks = relationship("AITask", back_populates="agent", cascade="all, delete-orphan")


class AITask(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    """A single unit of work submitted to an AI agent."""

    __tablename__ = "ai_tasks"
    __table_args__ = (Index("ix_ai_tasks_org_status", "organization_id", "status"),)

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_agents.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    triggered_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    objective: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent = relationship("AIAgent", back_populates="tasks")
    actions = relationship("AIAction", back_populates="task", cascade="all, delete-orphan")
    approvals = relationship("AIApproval", back_populates="task", cascade="all, delete-orphan")


class AIAction(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    """An individual action taken by an AI agent — one row per tool call."""

    __tablename__ = "ai_actions"
    __table_args__ = (Index("ix_ai_actions_org_status", "organization_id", "status"),)

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_tasks.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_agents.id"), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="STARTED")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    requires_approval: Mapped[bool] = mapped_column(default=False, nullable=False)
    approval_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_approvals.id"), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task = relationship("AITask", back_populates="actions")


class AIApproval(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    """Human approval required for a sensitive AI action."""

    __tablename__ = "ai_approvals"
    __table_args__ = (
        Index("ix_ai_approvals_org_status", "organization_id", "status"),
        # FK cycle: ai_actions.approval_id → ai_approvals.id, and ai_approvals.requested_action_id → ai_actions.id
        # use_alter lets Alembic/SQLAlchemy emit CREATE TABLE without the cycle-blocking FK,
        # then ALTER TABLE to add it. Without this, DROP TABLE fails on SQLite.
    )

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_tasks.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    requested_action_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_actions.id", use_alter=True, name="fk_ai_approvals_action"), nullable=True,
    )
    requested_by_agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_agents.id"), nullable=False)
    requested_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")  # PENDING|APPROVED|REJECTED|EXPIRED
    decided_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    task = relationship("AITask", back_populates="approvals")
