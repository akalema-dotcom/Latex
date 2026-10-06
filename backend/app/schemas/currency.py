"""
app/schemas/currency.py
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CurrencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    symbol: str
    decimal_places: int
    country_code: str
    locale: str
    is_active: bool


class ExchangeRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    base_currency: str
    quote_currency: str
    rate: Decimal
    provider: str
    fetched_at: datetime
    expires_at: datetime
    is_stale: bool


class ConvertIn(BaseModel):
    amount: Decimal = Field(..., max_digits=19, decimal_places=4)
    from_currency: str = Field(..., min_length=3, max_length=3)
    to_currency: str = Field(..., min_length=3, max_length=3)


class ConvertOut(BaseModel):
    amount: str
    from_currency: str
    to_currency: str
    exchange_rate: str
    converted_amount: str
    rate_provider: str
    rate_timestamp: datetime
    is_stale: bool
