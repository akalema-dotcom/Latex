"""
app/models/currency.py
======================
Currency + ExchangeRate models.

Currencies are seeded from the static catalog (currency_catalog.py).
Exchange rates can come from any provider via the ExchangeRateProvider
abstraction in app/services/exchange_rate_service.py.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Integer, Boolean, DateTime, Numeric, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin


class Currency(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False)
    decimal_places: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ExchangeRate(Base, UUIDPkMixin, TimestampMixin):
    """A single (base → quote) rate observation, with provider + expiry."""

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("base_currency", "quote_currency", "provider", name="uq_pair_provider"),
        Index("ix_exchange_rates_pair", "base_currency", "quote_currency"),
    )

    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)

    # The rate = how many units of quote_currency buy 1 unit of base_currency.
    # Example: base=USD, quote=UGX, rate=3650.25  →  1 USD = 3650.25 UGX
    rate: Mapped[float] = mapped_column(Numeric(19, 8), nullable=False)

    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Optional organization_id for organization-specific overrides
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True,
    )

    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
