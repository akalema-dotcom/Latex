"""
app/db/types.py
===============
Custom SQLAlchemy types for storing Decimal money values safely.

Money values MUST be stored as Numeric/DECIMAL — never as Float.
This module exposes a single ``Money`` type alias used across the models.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Numeric

# Two-decimal places is the default money precision. Some currencies (JPY, UGX)
# use 0 decimal places — those should override the precision at the column level.
DEFAULT_MONEY_PRECISION = 19
DEFAULT_MONEY_SCALE = 4  # 4 dp to keep FX conversion accuracy


def Money(precision: int = DEFAULT_MONEY_PRECISION, scale: int = DEFAULT_MONEY_SCALE):
    """Return a SQLAlchemy Numeric column type for monetary values."""
    return Numeric(precision=precision, scale=scale, asdecimal=True)


def round_money(value: Decimal, decimal_places: int = 2) -> Decimal:
    """Round a Decimal to N decimal places using banker's rounding variant."""
    if decimal_places == 0:
        quant = Decimal("1")
    else:
        quant = Decimal("1").scaleb(-decimal_places)
    return value.quantize(quant, rounding=ROUND_HALF_UP)
