"""
app/models/customer.py
"""
from __future__ import annotations

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin


class Customer(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    preferred_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    contacts = relationship("CustomerContact", back_populates="customer", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="customer")


class CustomerContact(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    __tablename__ = "customer_contacts"

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)

    customer = relationship("Customer", back_populates="contacts")
