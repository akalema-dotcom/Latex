"""
app/api/v1/endpoints/currencies.py
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.currency_catalog import get_currency as get_currency_info
from app.core.deps import get_current_user, get_db
from app.core.money import Money
from app.db.session import SessionLocal
from app.models.currency import Currency
from app.models.user import User
from app.schemas.currency import ConvertIn, ConvertOut, CurrencyOut, ExchangeRateOut
from app.services.exchange_rate_service import CurrencyService, CurrencyConversionError

router = APIRouter(tags=["currencies"])


def _ensure_currencies_seeded(db: Session) -> None:
    """Idempotently seed the currencies table from the static catalog."""
    from app.core.currency_catalog import list_currencies
    existing = {c.code for c in db.execute(select(Currency)).scalars()}
    if len(existing) >= len(list_currencies()):
        return
    for info in list_currencies():
        if info.code not in existing:
            db.add(Currency(
                code=info.code,
                name=info.name,
                symbol=info.symbol,
                decimal_places=info.decimal_places,
                country_code=info.country_code,
                locale=info.locale,
                is_active=info.is_active,
            ))
    db.flush()


@router.get("/currencies", response_model=list[CurrencyOut])
def list_currencies(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    _ensure_currencies_seeded(db)
    return list(db.execute(select(Currency).where(Currency.is_active.is_(True)).order_by(Currency.code)).scalars())


@router.get("/currencies/{code}", response_model=CurrencyOut)
def get_currency(
    code: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    _ensure_currencies_seeded(db)
    code = code.upper()
    cur = db.execute(select(Currency).where(Currency.code == code)).scalar_one_or_none()
    if not cur:
        raise HTTPException(status_code=404, detail=f"Currency {code} not found")
    return cur


@router.get("/exchange-rates", response_model=list[ExchangeRateOut])
def list_exchange_rates(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    base: Optional[str] = Query(default=None, min_length=3, max_length=3),
    quote: Optional[str] = Query(default=None, min_length=3, max_length=3),
):
    svc = CurrencyService(db)
    return svc.list_exchange_rates(base=base, quote=quote)


@router.get("/exchange-rates/{base}/{quote}", response_model=ExchangeRateOut)
def get_exchange_rate(
    base: str,
    quote: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    svc = CurrencyService(db)
    rates = svc.list_exchange_rates(base=base.upper(), quote=quote.upper())
    if not rates:
        raise HTTPException(status_code=404, detail="No exchange rate found")
    return rates[0]


@router.post("/currency/convert", response_model=ConvertOut)
def convert_currency(
    payload: ConvertIn,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    svc = CurrencyService(db)
    try:
        result = svc.convert(
            Money(amount=payload.amount, currency=payload.from_currency.upper()),
            to_currency=payload.to_currency.upper(),
        )
    except CurrencyConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ConvertOut(
        amount=str(result.original.amount),
        from_currency=result.original.currency,
        to_currency=result.converted.currency,
        exchange_rate=str(result.exchange_rate),
        converted_amount=str(result.converted.amount),
        rate_provider=result.rate_provider,
        rate_timestamp=result.rate_timestamp,
        is_stale=result.is_stale,
    )
