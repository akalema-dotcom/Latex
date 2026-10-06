"""
app/models/report.py
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin


REPORT_TYPES = ("monthly", "yearly", "profit_loss", "sales", "inventory", "tax", "custom")


class Report(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_org_type", "organization_id", "type"),)

    type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    generated_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    generated_by_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_agents.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
