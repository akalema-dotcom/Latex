"""
app/models/order.py
===================
Orders + Order items, with multi-currency support.

Each order preserves:
- the original currency it was placed in (currency)
- the original amount (total_amount)
- the exchange rate applied at the time
- the converted amount in the organization's base currency (base_amount)

The original currency and amount are IMMUTABLE after creation.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin
from app.db.types import Money


ORDER_STATUS = ("PENDING", "CONFIRMED", "PAID", "FULFILLED", "CANCELLED", "REFUNDED")


class Order(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_org_status", "organization_id", "status"),)

    order_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"), index=True, nullable=True,
    )

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")

    # --- Multi-currency ---
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))
    discount: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))
    tax: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))

    # Conversion metadata (immutable after creation)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Money(precision=19, scale=8), nullable=False, default=Decimal("1"))
    base_amount: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))

    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    placed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    placed_by_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_agents.id"), nullable=True)

    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="SET NULL"), index=True, nullable=True,
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Money(), nullable=False)

    # Cost of goods sold, for profit calculation (in order currency).
    unit_cost: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
