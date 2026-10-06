"""
app/models/transaction.py
"""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin
from app.db.types import Money


TRANSACTION_TYPES = ("SALE", "PURCHASE", "EXPENSE", "REFUND", "TAX", "FEE", "ADJUSTMENT")
TRANSACTION_FLOW = ("IN", "OUT")


class Transaction(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    """General ledger-style transaction record."""

    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_org_type", "organization_id", "type"),)

    reference: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    flow: Mapped[str] = mapped_column(String(4), nullable=False)  # IN | OUT

    amount: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Money(precision=19, scale=8), nullable=False, default=Decimal("1"))
    base_amount: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("orders.id"), nullable=True)
    purchase_order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("purchase_orders.id"), nullable=True)
    expense_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("expenses.id"), nullable=True)

    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
