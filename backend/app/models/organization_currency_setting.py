"""
app/models/organization_currency_setting.py
===========================================
Per-organization currency settings (manual rates, fallback rates, etc.).
"""
from __future__ import annotations

from sqlalchemy import String, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin, OrganizationFkMixin


class OrganizationCurrencySetting(Base, UUIDPkMixin, TimestampMixin, OrganizationFkMixin):
    """Per-organization currency overrides (manual exchange rates, etc.)."""

    __tablename__ = "organization_currency_settings"

    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Optional manual rate vs the organization's base currency
    manual_rate_to_base: Mapped[float | None] = mapped_column(Numeric(19, 6), nullable=True)

    organization = relationship("Organization", back_populates="currencies_settings")

    def __repr__(self) -> str:
        return f"<OrgCurrencySetting {self.currency_code} for {self.organization_id}>"
