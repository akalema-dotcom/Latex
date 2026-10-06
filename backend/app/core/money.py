"""
app/core/money.py
=================
Decimal-based Money value object.

CRITICAL: NEVER use Python floats for financial calculations.
This module enforces Decimal everywhere. The Money type is the only sanctioned
way to pass monetary amounts through the codebase.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Union

from app.core.currency_catalog import default_decimal_places, is_valid_currency_code


NumberLike = Union[Decimal, str, int, float]


def _to_decimal(value: NumberLike) -> Decimal:
    """
    Coerce arbitrary numeric input to Decimal.

    Floats are converted via str() to avoid binary representation errors
    (e.g. 0.1 + 0.2 = 0.30000000000000004). This is the recommended approach
    per the Python documentation.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, (int, str)):
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Cannot convert {value!r} to Decimal") from exc
    raise TypeError(f"Unsupported numeric type: {type(value).__name__}")


@dataclass(frozen=True)
class Money:
    """Immutable, currency-tagged monetary amount."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        # Normalize amount to Decimal (in case someone passed a str/int)
        object.__setattr__(self, "amount", _to_decimal(self.amount))
        # Validate currency code
        if not isinstance(self.currency, str) or not is_valid_currency_code(self.currency):
            raise ValueError(f"Invalid currency code: {self.currency!r}")

    # --- Arithmetic ---
    def __add__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: NumberLike) -> "Money":
        return Money(self.amount * _to_decimal(factor), self.currency)

    __rmul__ = __mul__

    def __truediv__(self, divisor: NumberLike) -> "Money":
        d = _to_decimal(divisor)
        if d == 0:
            raise ZeroDivisionError("Cannot divide Money by zero")
        return Money(self.amount / d, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    # --- Comparisons ---
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == other.amount and self.currency == other.currency

    def __lt__(self, other: "Money") -> bool:
        self._require_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._require_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: "Money") -> bool:
        self._require_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: "Money") -> bool:
        self._require_same_currency(other)
        return self.amount >= other.amount

    def is_zero(self) -> bool:
        return self.amount == 0

    def is_positive(self) -> bool:
        return self.amount > 0

    def is_negative(self) -> bool:
        return self.amount < 0

    # --- Helpers ---
    def _require_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Currency mismatch: {self.currency} vs {other.currency}"
            )

    def round_to_currency(self) -> "Money":
        """Round to the currency's standard decimal places (ISO 4217)."""
        from app.db.types import round_money
        dp = default_decimal_places(self.currency)
        return Money(round_money(self.amount, dp), self.currency)

    def to_dict(self) -> dict:
        return {"amount": str(self.amount), "currency": self.currency}

    @classmethod
    def zero(cls, currency: str) -> "Money":
        return cls(Decimal("0"), currency)

    @classmethod
    def from_dict(cls, data: dict) -> "Money":
        return cls(amount=data["amount"], currency=data["currency"])
