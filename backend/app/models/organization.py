"""
app/models/organization.py
==========================
Organization / tenant model.

Every business is an organization. An organization selects its own country,
currency, locale and timezone. USD is the system-wide default, but the
organization's base_currency can override that.
"""
from __future__ import annotations

from sqlalchemy import Boolean, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin


class Organization(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # --- Localization ---
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", index=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en-US")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    # --- Business settings ---
    tax_rate_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0–100
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="free")

    # --- Relationships (lazy) ---
    users = relationship("User", back_populates="organization", lazy="selectin")
    currencies_settings = relationship(
        "OrganizationCurrencySetting", back_populates="organization", lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug} ({self.base_currency})>"


# Separate file import to avoid circular import — declared here for compactness.
from app.models.organization_currency_setting import OrganizationCurrencySetting  # noqa: E402
