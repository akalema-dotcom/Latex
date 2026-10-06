"""
app/models/product.py
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import String, Boolean, Numeric, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin
from app.db.types import Money


class Product(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_org_sku", "organization_id", "sku"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Pricing in the organization's base currency.
    # Decimal — never float.
    price: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))
    cost: Mapped[Decimal] = mapped_column(Money(), nullable=False, default=Decimal("0"))

    # Inventory threshold below which an auto-reorder can be triggered.
    reorder_threshold: Mapped[int] = mapped_column(default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    inventory = relationship("Inventory", back_populates="product", uselist=False, cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="product")
