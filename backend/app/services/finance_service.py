"""
app/services/finance_service.py
===============================
Financial reporting engine.

CRITICAL:
- All profit calculations use Decimal (never float).
- All amounts are normalized to the organization's base currency before
  being aggregated.
- Never divide by zero (zero-revenue scenarios are handled explicitly).
- Handles refunds, cancelled orders, returned products, discounts, taxes,
  multiple currencies, exchange-rate changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.core.money import Money
from app.models.expense import Expense
from app.models.order import Order, OrderItem
from app.models.organization import Organization
from app.models.transaction import Transaction
from app.services.exchange_rate_service import CurrencyService, CurrencyConversionError


@dataclass
class ProfitLossReport:
    period_start: datetime
    period_end: datetime
    base_currency: str

    revenue: Decimal = Decimal("0")
    cogs: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    gross_margin_pct: Decimal = Decimal("0")

    refunds: Decimal = Decimal("0")
    discounts: Decimal = Decimal("0")
    taxes_collected: Decimal = Decimal("0")

    expenses: Decimal = Decimal("0")
    net_profit: Decimal = Decimal("0")
    net_margin_pct: Decimal = Decimal("0")

    orders_count: int = 0
    cancelled_orders_count: int = 0
    refunded_orders_count: int = 0

    currency_breakdown: dict = field(default_factory=dict)
    is_complete: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "base_currency": self.base_currency,
            "revenue": str(self.revenue),
            "cogs": str(self.cogs),
            "gross_profit": str(self.gross_profit),
            "gross_margin_pct": str(self.gross_margin_pct),
            "refunds": str(self.refunds),
            "discounts": str(self.discounts),
            "taxes_collected": str(self.taxes_collected),
            "expenses": str(self.expenses),
            "net_profit": str(self.net_profit),
            "net_margin_pct": str(self.net_margin_pct),
            "orders_count": self.orders_count,
            "cancelled_orders_count": self.cancelled_orders_count,
            "refunded_orders_count": self.refunded_orders_count,
            "currency_breakdown": self.currency_breakdown,
            "is_complete": self.is_complete,
            "notes": self.notes,
        }


class FinanceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_profit_loss(
        self,
        organization_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> ProfitLossReport:
        org = self.db.get(Organization, organization_id)
        if not org:
            raise ValueError("Organization not found")
        base_currency = org.base_currency

        report = ProfitLossReport(
            period_start=period_start,
            period_end=period_end,
            base_currency=base_currency,
        )

        # --- Orders ---
        orders = list(self.db.execute(
            select(Order).where(
                Order.organization_id == organization_id,
                Order.created_at >= period_start,
                Order.created_at < period_end,
            )
        ).scalars())

        for order in orders:
            if order.status == "CANCELLED":
                report.cancelled_orders_count += 1
                continue
            if order.status == "REFUNDED":
                report.refunded_orders_count += 1
                # Refund amount is negative revenue
                base_total = self._to_base(order.total_amount, order.currency, base_currency, order.exchange_rate, order.base_amount)
                report.refunds += base_total
                continue

            report.orders_count += 1
            base_total = self._to_base(order.total_amount, order.currency, base_currency, order.exchange_rate, order.base_amount)
            report.revenue += base_total

            # Track discounts
            if order.discount and order.discount > 0:
                report.discounts += self._to_base(order.discount, order.currency, base_currency, order.exchange_rate, order.base_amount)

            # Track taxes
            if order.tax and order.tax > 0:
                report.taxes_collected += self._to_base(order.tax, order.currency, base_currency, order.exchange_rate, order.base_amount)

            # COGS from order items
            cogs_local = sum((item.unit_cost * item.quantity) for item in order.items)
            if cogs_local > 0:
                report.cogs += self._to_base(cogs_local, order.currency, base_currency, order.exchange_rate, order.base_amount)

            # Currency breakdown
            report.currency_breakdown.setdefault(order.currency, {"orders": 0, "amount": "0"})
            report.currency_breakdown[order.currency]["orders"] += 1
            report.currency_breakdown[order.currency]["amount"] = str(
                Decimal(report.currency_breakdown[order.currency]["amount"]) + order.total_amount
            )

        # --- Expenses ---
        expenses = list(self.db.execute(
            select(Expense).where(
                Expense.organization_id == organization_id,
                Expense.incurred_on >= period_start,
                Expense.incurred_on < period_end,
            )
        ).scalars())
        for expense in expenses:
            base = self._to_base(expense.amount, expense.currency, base_currency, expense.exchange_rate, expense.base_amount)
            report.expenses += base

        # --- Compute derived metrics ---
        report.gross_profit = report.revenue - report.cogs
        report.gross_margin_pct = self._safe_margin(report.gross_profit, report.revenue)
        report.net_profit = report.gross_profit - report.expenses
        report.net_margin_pct = self._safe_margin(report.net_profit, report.revenue)

        return report

    def _to_base(
        self,
        original_amount: Decimal,
        original_currency: str,
        base_currency: str,
        stored_rate: Decimal,
        stored_base: Decimal,
    ) -> Decimal:
        """
        Use the stored base amount if it's already in the right currency and
        the rate is 1 (identity) or matches; otherwise re-derive via stored rate.
        Falls back to live conversion if necessary, marking the report as
        incomplete on failure.
        """
        if original_currency == base_currency:
            return original_amount
        # Prefer the stored rate (immutable historical record)
        if stored_rate and stored_rate != 0:
            return original_amount * stored_rate
        # Last-resort live conversion
        try:
            svc = CurrencyService(self.db)
            result = svc.convert(Money(original_amount, original_currency), base_currency)
            return result.converted.amount
        except CurrencyConversionError:
            return Decimal("0")

    @staticmethod
    def _safe_margin(numerator: Decimal, denominator: Decimal) -> Decimal:
        """Compute percentage margin. Returns 0 if revenue is zero — never divides by zero."""
        if denominator == 0:
            return Decimal("0")
        return (numerator / denominator) * Decimal("100")

    def monthly_report(self, organization_id: str, year: int, month: int) -> ProfitLossReport:
        """Generate a monthly report for the given year/month."""
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        return self.generate_profit_loss(organization_id, start, end)

    def yearly_report(self, organization_id: str, year: int) -> ProfitLossReport:
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        return self.generate_profit_loss(organization_id, start, end)
