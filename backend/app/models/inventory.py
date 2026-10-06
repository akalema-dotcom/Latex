"""
app/models/inventory.py
"""
from __future__ import annotations

from sqlalchemy import String, Integer, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin


class Inventory(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "inventory"
    __table_args__ = {"sqlite_autoincrement": True}

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    location: Mapped[str | None] = mapped_column(String(64), nullable=True)

    product = relationship("Product", back_populates="inventory")
    movements = relationship("InventoryMovement", back_populates="inventory", cascade="all, delete-orphan")


class InventoryMovement(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    """An immutable record of every inventory change (audit-friendly)."""

    __tablename__ = "inventory_movements"

    inventory_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    # IN, OUT, ADJUSTMENT, RETURN, RECEIVED
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    inventory = relationship("Inventory", back_populates="movements")
