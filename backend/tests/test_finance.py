"""
tests/test_finance.py
=====================
Finance engine tests.

Covers: revenue, COGS, gross profit, net profit, margins, refunds, expenses,
multiple currencies, zero-revenue scenarios.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.models.customer import Customer
from app.models.expense import Expense
from app.models.inventory import Inventory
from app.models.order import Order, OrderItem
from app.models.organization import Organization
from app.models.product import Product
from app.services.finance_service import FinanceService


def _seed_org(db, currency="UGX", country="UG", tax=18):
    org = Organization(
        name="Test Org", slug=f"test-{currency.lower()}",
        country_code=country, base_currency=currency,
        locale="en-UG", timezone="Africa/Kampala",
        tax_rate_pct=tax,
    )
    db.add(org)
    db.flush()
    return org


def _seed_order(db, org, customer, product, qty, currency=None, status="PAID"):
    currency = currency or org.base_currency
    line_total = product.price * qty
    order = Order(
        organization_id=org.id, order_number=f"ORD-{datetime.now(timezone.utc).timestamp()}",
        customer_id=customer.id, status=status,
        currency=currency, subtotal=line_total,
        discount=Decimal("0"), tax=Decimal("0"),
        total_amount=line_total,
        base_currency=org.base_currency, exchange_rate=Decimal("1"),
        base_amount=line_total if currency == org.base_currency else Decimal("0"),
        paid_at=datetime.now(timezone.utc) if status == "PAID" else None,
    )
    db.add(order)
    db.flush()
    db.add(OrderItem(
        organization_id=org.id, order_id=order.id, product_id=product.id,
        product_name=product.name, quantity=qty,
        unit_price=product.price, line_total=line_total,
        unit_cost=product.cost,
    ))
    return order


def test_revenue_and_cogs(db_session):
    org = _seed_org(db_session, currency="UGX")
    cust = Customer(organization_id=org.id, name="Cust")
    db_session.add(cust)
    db_session.flush()
    prod = Product(
        organization_id=org.id, name="Widget", sku="W1",
        price=Decimal("100000"), cost=Decimal("60000"),
    )
    db_session.add(prod)
    db_session.flush()
    _seed_order(db_session, org, cust, prod, qty=2)
    db_session.commit()

    svc = FinanceService(db_session)
    report = svc.monthly_report(org.id, datetime.now(timezone.utc).year, datetime.now(timezone.utc).month)
    assert report.revenue == Decimal("200000")  # 100000 * 2
    assert report.cogs == Decimal("120000")     # 60000 * 2
    assert report.gross_profit == Decimal("80000")
    assert report.gross_margin_pct == Decimal("40")


def test_zero_revenue_no_division_by_zero(db_session):
    org = _seed_org(db_session)
    svc = FinanceService(db_session)
    report = svc.yearly_report(org.id, 1900)
    assert report.revenue == Decimal("0")
    assert report.gross_margin_pct == Decimal("0")
    assert report.net_margin_pct == Decimal("0")


def test_expense_reduces_net_profit(db_session):
    org = _seed_org(db_session, currency="UGX")
    cust = Customer(organization_id=org.id, name="Cust")
    db_session.add(cust)
    db_session.flush()
    prod = Product(
        organization_id=org.id, name="Widget", sku="W1",
        price=Decimal("100000"), cost=Decimal("60000"),
    )
    db_session.add(prod)
    db_session.flush()
    _seed_order(db_session, org, cust, prod, qty=1)
    db_session.add(Expense(
        organization_id=org.id, category="rent", description="Office",
        amount=Decimal("20000"), currency="UGX",
        base_currency="UGX", exchange_rate=Decimal("1"), base_amount=Decimal("20000"),
        incurred_on=datetime.now(timezone.utc),
    ))
    db_session.commit()

    svc = FinanceService(db_session)
    report = svc.monthly_report(org.id, datetime.now(timezone.utc).year, datetime.now(timezone.utc).month)
    assert report.revenue == Decimal("100000")
    assert report.gross_profit == Decimal("40000")
    assert report.expenses == Decimal("20000")
    assert report.net_profit == Decimal("20000")
    assert report.net_margin_pct == Decimal("20")


def test_cancelled_orders_excluded_from_revenue(db_session):
    org = _seed_org(db_session, currency="UGX")
    cust = Customer(organization_id=org.id, name="Cust")
    db_session.add(cust)
    db_session.flush()
    prod = Product(
        organization_id=org.id, name="Widget", sku="W1",
        price=Decimal("100000"), cost=Decimal("60000"),
    )
    db_session.add(prod)
    db_session.flush()
    _seed_order(db_session, org, cust, prod, qty=1, status="PAID")
    _seed_order(db_session, org, cust, prod, qty=1, status="CANCELLED")
    db_session.commit()

    svc = FinanceService(db_session)
    report = svc.monthly_report(org.id, datetime.now(timezone.utc).year, datetime.now(timezone.utc).month)
    assert report.revenue == Decimal("100000")  # only the PAID one
    assert report.cancelled_orders_count == 1


def test_refunded_orders_tracked_separately(db_session):
    org = _seed_org(db_session, currency="UGX")
    cust = Customer(organization_id=org.id, name="Cust")
    db_session.add(cust)
    db_session.flush()
    prod = Product(
        organization_id=org.id, name="Widget", sku="W1",
        price=Decimal("100000"), cost=Decimal("60000"),
    )
    db_session.add(prod)
    db_session.flush()
    _seed_order(db_session, org, cust, prod, qty=1, status="PAID")
    _seed_order(db_session, org, cust, prod, qty=1, status="REFUNDED")
    db_session.commit()

    svc = FinanceService(db_session)
    report = svc.monthly_report(org.id, datetime.now(timezone.utc).year, datetime.now(timezone.utc).month)
    assert report.revenue == Decimal("100000")  # only the PAID one
    assert report.refunds == Decimal("100000")  # the refunded one
    assert report.refunded_orders_count == 1


def test_yearly_report_aggregates_all_months(db_session):
    org = _seed_org(db_session, currency="USD")
    cust = Customer(organization_id=org.id, name="Cust")
    db_session.add(cust)
    db_session.flush()
    prod = Product(
        organization_id=org.id, name="Widget", sku="W1",
        price=Decimal("100"), cost=Decimal("60"),
    )
    db_session.add(prod)
    db_session.flush()
    _seed_order(db_session, org, cust, prod, qty=5)
    db_session.commit()

    svc = FinanceService(db_session)
    report = svc.yearly_report(org.id, datetime.now(timezone.utc).year)
    assert report.revenue == Decimal("500")
    assert report.cogs == Decimal("300")
    assert report.gross_profit == Decimal("200")


def test_organization_can_use_eur_as_base(db_session):
    org = _seed_org(db_session, currency="EUR", country="DE")
    cust = Customer(organization_id=org.id, name="Cust")
    db_session.add(cust)
    db_session.flush()
    prod = Product(
        organization_id=org.id, name="Widget", sku="W1",
        price=Decimal("500"), cost=Decimal("300"),
    )
    db_session.add(prod)
    db_session.flush()
    _seed_order(db_session, org, cust, prod, qty=1)
    db_session.commit()

    svc = FinanceService(db_session)
    report = svc.monthly_report(org.id, datetime.now(timezone.utc).year, datetime.now(timezone.utc).month)
    assert report.base_currency == "EUR"
    assert report.revenue == Decimal("500")
    assert report.gross_profit == Decimal("200")


def test_organization_can_use_usd_as_base(db_session):
    org = _seed_org(db_session, currency="USD", country="US")
    cust = Customer(organization_id=org.id, name="Cust")
    db_session.add(cust)
    db_session.flush()
    prod = Product(
        organization_id=org.id, name="Widget", sku="W1",
        price=Decimal("100"), cost=Decimal("60"),
    )
    db_session.add(prod)
    db_session.flush()
    _seed_order(db_session, org, cust, prod, qty=1)
    db_session.commit()

    svc = FinanceService(db_session)
    report = svc.monthly_report(org.id, datetime.now(timezone.utc).year, datetime.now(timezone.utc).month)
    assert report.base_currency == "USD"
    assert report.revenue == Decimal("100")
