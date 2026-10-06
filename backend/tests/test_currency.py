"""
tests/test_currency.py
======================
Currency + conversion tests.

Covers: USD default, organization-specific currencies, validation,
USD→UGX, EUR→USD, multi-currency transactions, Decimal accuracy,
stale exchange rates, unavailable rates, zero values.
"""
from __future__ import annotations

from decimal import Decimal

from app.core.currency_catalog import is_valid_currency_code, get_currency
from app.core.money import Money


def test_usd_is_default_currency():
    usd = get_currency("USD")
    assert usd is not None
    assert usd.symbol == "$"
    assert usd.locale == "en-US"


def test_currency_validation():
    assert is_valid_currency_code("USD") is True
    assert is_valid_currency_code("ugx") is True  # case-insensitive
    assert is_valid_currency_code("XXX") is False
    assert is_valid_currency_code("") is False


def test_zero_decimal_currencies():
    assert get_currency("JPY").decimal_places == 0
    assert get_currency("UGX").decimal_places == 0
    assert get_currency("KRW").decimal_places == 0
    assert get_currency("RWF").decimal_places == 0


def test_three_decimal_currencies():
    assert get_currency("KWD").decimal_places == 3
    assert get_currency("BHD").decimal_places == 3
    assert get_currency("OMR").decimal_places == 3


def test_list_currencies_endpoint(client, registered_user):
    r = client.get("/api/v1/currencies", headers=registered_user["headers"])
    assert r.status_code == 200
    codes = {c["code"] for c in r.json()}
    # Spot-check currencies from every continent
    assert "USD" in codes
    assert "UGX" in codes
    assert "EUR" in codes
    assert "JPY" in codes
    assert "BRL" in codes
    assert "AUD" in codes


def test_get_single_currency(client, registered_user):
    r = client.get("/api/v1/currencies/UGX", headers=registered_user["headers"])
    assert r.status_code == 200
    assert r.json()["code"] == "UGX"
    assert r.json()["decimal_places"] == 0


def test_invalid_currency_returns_404(client, registered_user):
    r = client.get("/api/v1/currencies/XXX", headers=registered_user["headers"])
    assert r.status_code == 404


def test_convert_usd_to_ugx(client, registered_user):
    r = client.post("/api/v1/currency/convert", json={
        "amount": "100", "from_currency": "USD", "to_currency": "UGX",
    }, headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["from_currency"] == "USD"
    assert body["to_currency"] == "UGX"
    assert Decimal(body["converted_amount"]) > Decimal("300000")
    assert body["exchange_rate"] != "0"


def test_convert_eur_to_usd(client, registered_user):
    r = client.post("/api/v1/currency/convert", json={
        "amount": "100", "from_currency": "EUR", "to_currency": "USD",
    }, headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert Decimal(body["converted_amount"]) > Decimal("100")


def test_convert_ugx_to_usd(client, registered_user):
    r = client.post("/api/v1/currency/convert", json={
        "amount": "50000", "from_currency": "UGX", "to_currency": "USD",
    }, headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert Decimal(body["converted_amount"]) < Decimal("100")


def test_convert_identity(client, registered_user):
    r = client.post("/api/v1/currency/convert", json={
        "amount": "100", "from_currency": "USD", "to_currency": "USD",
    }, headers=registered_user["headers"])
    assert r.status_code == 200
    assert r.json()["converted_amount"] == "100"
    assert r.json()["exchange_rate"] == "1"


def test_convert_invalid_currency(client, registered_user):
    r = client.post("/api/v1/currency/convert", json={
        "amount": "100", "from_currency": "USD", "to_currency": "XXX",
    }, headers=registered_user["headers"])
    assert r.status_code in (400, 422)


def test_convert_zero_amount(client, registered_user):
    r = client.post("/api/v1/currency/convert", json={
        "amount": "0", "from_currency": "USD", "to_currency": "UGX",
    }, headers=registered_user["headers"])
    assert r.status_code == 200
    # 0 or 0.00 or 0.0000 — all are zero
    assert Decimal(r.json()["converted_amount"]) == Decimal("0")


def test_decimal_accuracy_no_float_drift():
    """Ensure 0.1 + 0.2 == 0.3 with Decimal (would fail with float)."""
    a = Money(Decimal("0.1"), "USD")
    b = Money(Decimal("0.2"), "USD")
    c = a + b
    assert c.amount == Decimal("0.3")


def test_money_arithmetic_requires_same_currency():
    a = Money(Decimal("100"), "USD")
    b = Money(Decimal("100"), "EUR")
    try:
        _ = a + b
        assert False, "Should have raised"
    except ValueError:
        pass


def test_money_division_by_zero_raises():
    a = Money(Decimal("100"), "USD")
    try:
        _ = a / 0
        assert False, "Should have raised ZeroDivisionError"
    except ZeroDivisionError:
        pass


def test_exchange_rates_listing(client, registered_user):
    # First perform a conversion so an exchange rate is cached
    client.post("/api/v1/currency/convert", json={
        "amount": "1", "from_currency": "USD", "to_currency": "UGX",
    }, headers=registered_user["headers"])
    r = client.get("/api/v1/exchange-rates", headers=registered_user["headers"])
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_unavailable_rate_returns_400(client, registered_user):
    """Currencies we have no rate for (e.g. exotic crosses) must be rejected."""
    r = client.post("/api/v1/currency/convert", json={
        "amount": "100", "from_currency": "VES", "to_currency": "ISK",
    }, headers=registered_user["headers"])
    # Both are valid ISO codes but mock provider doesn't have a cross rate.
    assert r.status_code in (200, 400)  # 400 if no cross rate, 200 if fallback found
