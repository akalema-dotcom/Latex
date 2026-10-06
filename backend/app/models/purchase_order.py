"""
app/models/purchase_order.py
"""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin
from app.db.types import Money


PURCHASE_ORDER_STATUS = ("DRAFT", "SUBMITTED", "APPROVED", "RECEIVED", "CANCELLED")


class PurchaseOrder(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "purchase_orders"
    __table_args__ = (Index("ix_purchase_orders_org_status", "organization_id", "status"),)

    po_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True, nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")

    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))

    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Money(precision=19, scale=8), nullable=False, default=Decimal("1"))
    base_amount: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))

    expected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_by_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_agents.id"), nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    supplier = relationship("Supplier", back_populates="purchase_orders")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="SET NULL"), index=True, nullable=True,
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Money(), nullable=False)

    purchase_order = relationship("PurchaseOrder", back_populates="items")
