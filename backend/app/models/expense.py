"""
app/models/expense.py
"""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin
from app.db.types import Money


class Expense(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expenses_org_category", "organization_id", "category"),)

    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Money(precision=19, scale=8), nullable=False, default=Decimal("1"))
    base_amount: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))

    incurred_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
