"""
app/services/exchange_rate_service.py
=====================================
Currency conversion service + provider abstraction.

The conversion service:
- validates currency codes
- uses Decimal everywhere
- stores the exchange rate used
- supports cached / live / manual rates
- marks rates as stale when they expire (NEVER silently uses an expired rate
  as if it were current)
- supports multiple providers via the ExchangeRateProvider interface
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.currency_catalog import is_valid_currency_code
from app.core.money import Money, _to_decimal
from app.models.currency import Currency, ExchangeRate


# ===========================================================================
# Provider abstraction
# ===========================================================================
class ExchangeRateProvider(ABC):
    """Interface every exchange-rate provider must implement."""

    name: str = "abstract"

    @abstractmethod
    def fetch_rate(self, base: str, quote: str) -> Optional[Decimal]:
        """Return the rate (1 base = X quote) or None if unavailable."""
        raise NotImplementedError


class ManualRateProvider(ExchangeRateProvider):
    """
    No live source. Rates must be pre-populated in the exchange_rates table.
    Useful for sandboxed deployments or organizations with manually-set rates.
    """

    name = "manual"

    def fetch_rate(self, base: str, quote: str) -> Optional[Decimal]:
        return None  # caller falls back to DB lookup


class MockRateProvider(ExchangeRateProvider):
    """
    Deterministic mock rates for development / testing. Uses simple lookup
    so tests are reproducible without an external service.
    """

    name = "mock"
    # Updated Oct 2024-ish; purely for local dev. NEVER used in production.
    _RATES = {
        ("USD", "UGX"): Decimal("3650.25"),
        ("USD", "KES"): Decimal("129.50"),
        ("USD", "TZS"): Decimal("2530.00"),
        ("USD", "RWF"): Decimal("1280.00"),
        ("USD", "NGN"): Decimal("1580.00"),
        ("USD", "ZAR"): Decimal("18.20"),
        ("USD", "EUR"): Decimal("0.92"),
        ("USD", "GBP"): Decimal("0.79"),
        ("USD", "JPY"): Decimal("149.50"),
        ("USD", "INR"): Decimal("83.30"),
        ("USD", "CNY"): Decimal("7.18"),
        ("USD", "AED"): Decimal("3.67"),
        ("USD", "SAR"): Decimal("3.75"),
        ("USD", "CAD"): Decimal("1.36"),
        ("USD", "AUD"): Decimal("1.52"),
        ("USD", "CHF"): Decimal("0.88"),
    }

    def fetch_rate(self, base: str, quote: str) -> Optional[Decimal]:
        if base == quote:
            return Decimal("1")
        if (base, quote) in self._RATES:
            return self._RATES[(base, quote)]
        # Compute via USD cross-rate
        # 1 base = X USD  and  1 USD = Y quote  →  1 base = X*Y quote
        if base == "USD":
            usd_base = Decimal("1")
        elif (base, "USD") in self._RATES:
            usd_base = self._RATES[(base, "USD")]
        elif ("USD", base) in self._RATES:
            usd_base = Decimal("1") / self._RATES[("USD", base)]
        else:
            return None

        if quote == "USD":
            usd_quote = Decimal("1")
        elif ("USD", quote) in self._RATES:
            usd_quote = self._RATES[("USD", quote)]
        elif (quote, "USD") in self._RATES:
            usd_quote = Decimal("1") / self._RATES[(quote, "USD")]
        else:
            return None

        return usd_base * usd_quote


class FrankfurterProvider(ExchangeRateProvider):
    """
    Live provider: Frankfurter.app — free, open-source ECB rates.
    No API key required. Returns latest rates against EUR or USD.
    """

    name = "frankfurter"
    BASE_URL = "https://api.frankfurter.app/latest"

    def fetch_rate(self, base: str, quote: str) -> Optional[Decimal]:
        if base == quote:
            return Decimal("1")
        try:
            r = httpx.get(self.BASE_URL, params={"from": base, "to": quote}, timeout=10.0)
            r.raise_for_status()
            data = r.json()
            rate = data.get("rates", {}).get(quote)
            return _to_decimal(rate) if rate else None
        except Exception:
            return None


class OpenExchangeRatesProvider(ExchangeRateProvider):
    """OpenExchangeRates — requires app_id."""

    name = "openexchangerates"
    BASE_URL = "https://openexchangerates.org/api/latest.json"

    def fetch_rate(self, base: str, quote: str) -> Optional[Decimal]:
        if base == quote:
            return Decimal("1")
        if not settings.OPENEXCHANGERATES_APP_ID:
            return None
        try:
            r = httpx.get(
                self.BASE_URL,
                params={"app_id": settings.OPENEXCHANGERATES_APP_ID, "base": "USD"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
            rates = data.get("rates", {})
            usd_base = _to_decimal(rates.get(base)) if base != "USD" else Decimal("1")
            usd_quote = _to_decimal(rates.get(quote)) if quote != "USD" else Decimal("1")
            if not usd_base or not usd_quote:
                return None
            return (usd_quote / usd_base) if usd_base else None
        except Exception:
            return None


# ===========================================================================
# Provider registry
# ===========================================================================
def get_provider(name: str | None = None) -> ExchangeRateProvider:
    name = name or settings.EXCHANGE_RATE_PROVIDER
    mapping = {
        "mock": MockRateProvider,
        "manual": ManualRateProvider,
        "frankfurter": FrankfurterProvider,
        "openexchangerates": OpenExchangeRatesProvider,
    }
    cls = mapping.get(name, MockRateProvider)
    return cls()


# ===========================================================================
# Service
# ===========================================================================
@dataclass
class ConversionResult:
    original: Money
    converted: Money
    exchange_rate: Decimal
    rate_provider: str
    rate_timestamp: datetime
    is_stale: bool


class CurrencyConversionError(Exception):
    pass


class CurrencyService:
    """High-level currency conversion + rate persistence."""

    def __init__(self, db: Session, provider: ExchangeRateProvider | None = None) -> None:
        self.db = db
        self.provider = provider or get_provider()

    # ----- public API -----
    def convert(self, amount: Money, to_currency: str) -> ConversionResult:
        """Convert a Money amount to a target currency."""
        if not is_valid_currency_code(to_currency):
            raise CurrencyConversionError(f"Invalid currency code: {to_currency}")
        if amount.currency == to_currency:
            return ConversionResult(
                original=amount,
                converted=Money(amount.amount, to_currency),
                exchange_rate=Decimal("1"),
                rate_provider="identity",
                rate_timestamp=datetime.now(timezone.utc),
                is_stale=False,
            )

        rate, provider_name, fetched_at, is_stale = self._get_or_fetch_rate(
            amount.currency, to_currency,
        )
        if rate is None:
            raise CurrencyConversionError(
                f"No exchange rate available for {amount.currency}→{to_currency}"
            )
        converted_amount = (amount.amount * rate)
        return ConversionResult(
            original=amount,
            converted=Money(converted_amount, to_currency),
            exchange_rate=rate,
            rate_provider=provider_name,
            rate_timestamp=fetched_at,
            is_stale=is_stale,
        )

    # ----- internals -----
    def _get_or_fetch_rate(
        self, base: str, quote: str,
    ) -> tuple[Decimal | None, str, datetime, bool]:
        """Try DB cache first, then live provider. Persist new live rates."""
        now = datetime.now(timezone.utc)
        cache_ttl = timedelta(seconds=settings.EXCHANGE_RATE_CACHE_SECONDS)
        stale_after = timedelta(seconds=settings.EXCHANGE_RATE_STALE_SECONDS)

        # 1) Look up cached rate
        cached = self._lookup_cached_rate(base, quote)
        if cached:
            age = now - cached.fetched_at
            if age < cache_ttl:
                return cached.rate, cached.provider, cached.fetched_at, False
            # Expired cache → try live, fall back to stale if no live rate.
            live = self.provider.fetch_rate(base, quote)
            if live is not None:
                self._upsert_rate(base, quote, live, self.provider.name, now, now + cache_ttl)
                return live, self.provider.name, now, False
            # Live unavailable — return stale but explicitly flagged.
            if age < stale_after:
                return cached.rate, cached.provider, cached.fetched_at, True
            return None, cached.provider, cached.fetched_at, True

        # 2) No cached rate — try live provider
        live = self.provider.fetch_rate(base, quote)
        if live is not None:
            self._upsert_rate(base, quote, live, self.provider.name, now, now + cache_ttl)
            return live, self.provider.name, now, False
        return None, "unknown", now, True

    def _lookup_cached_rate(self, base: str, quote: str) -> ExchangeRate | None:
        stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.base_currency == base)
            .where(ExchangeRate.quote_currency == quote)
            .where(ExchangeRate.organization_id.is_(None))
            .order_by(ExchangeRate.fetched_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _upsert_rate(
        self, base: str, quote: str, rate: Decimal, provider: str,
        fetched_at: datetime, expires_at: datetime,
    ) -> None:
        existing = self._lookup_cached_rate(base, quote)
        if existing:
            existing.rate = rate
            existing.provider = provider
            existing.fetched_at = fetched_at
            existing.expires_at = expires_at
            existing.is_stale = False
        else:
            new_rate = ExchangeRate(
                base_currency=base,
                quote_currency=quote,
                rate=rate,
                provider=provider,
                fetched_at=fetched_at,
                expires_at=expires_at,
                is_stale=False,
            )
            self.db.add(new_rate)
        self.db.flush()

    # ----- maintenance -----
    def list_currencies(self) -> list[Currency]:
        return list(self.db.execute(select(Currency).where(Currency.is_active.is_(True))).scalars())

    def get_currency(self, code: str) -> Currency | None:
        return self.db.execute(
            select(Currency).where(Currency.code == code.upper())
        ).scalar_one_or_none()

    def list_exchange_rates(self, base: str | None = None, quote: str | None = None) -> list[ExchangeRate]:
        stmt = select(ExchangeRate).order_by(ExchangeRate.fetched_at.desc())
        if base:
            stmt = stmt.where(ExchangeRate.base_currency == base.upper())
        if quote:
            stmt = stmt.where(ExchangeRate.quote_currency == quote.upper())
        return list(self.db.execute(stmt).scalars())
