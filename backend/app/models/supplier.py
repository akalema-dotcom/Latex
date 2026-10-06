"""
app/models/supplier.py
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import String, Numeric, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin
from app.db.types import Money


class Supplier(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    products = relationship("SupplierProduct", back_populates="supplier", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")


class SupplierProduct(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "supplier_products"

    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    supplier_sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supplier_price: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    lead_time_days: Mapped[int] = mapped_column(default=7, nullable=False)
    min_order_qty: Mapped[int] = mapped_column(default=1, nullable=False)

    supplier = relationship("Supplier", back_populates="products")
    product = relationship("Product")
