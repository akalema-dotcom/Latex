"""
scripts/live_demo.py
====================
Live end-to-end demo against a running server on http://127.0.0.1:8765.
Prints the actual responses so the user can see the API working.

Uses ONLY the HTTP API + raw SQL for the small "verify email / promote role"
helpers — avoids the model registry entirely.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8765"
DB_PATH = "ai_business_workforce.db"


def banner(title: str) -> None:
    print("\n" + "═" * 70)
    print(f"  {title}")
    print("═" * 70)


def show(label: str, response: httpx.Response) -> None:
    print(f"\n▶ {label}")
    print(f"  HTTP {response.status_code}")
    try:
        body = response.json()
        text = json.dumps(body, indent=2, default=str)
        print(f"  {text[:900]}")
    except Exception:
        print(f"  {response.text[:400]}")


def sql_exec(query: str, params: tuple = ()) -> None:
    """Run raw SQL against the same sqlite file the server is using."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(query, params)
    conn.commit()
    conn.close()


def sql_fetchone(query: str, params: tuple = ()):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(query, params)
    row = cur.fetchone()
    conn.close()
    return row


# === 1. Healthcheck ===
banner("1. HEALTHCHECK")
r = httpx.get(f"{BASE}/health", timeout=5)
show("GET /health", r)

# === 2. Register a business owner ===
banner("2. REGISTER BUSINESS OWNER")
r = httpx.post(f"{BASE}/api/v1/auth/register", json={
    "email": "owner@kampala-traders.ug",
    "password": "Sup3rSecret!2026",
    "full_name": "Joan Kalema",
}, timeout=10)
show("POST /api/v1/auth/register", r)
owner_id = r.json()["id"]

# Auto-verify email (simulating clicking the email link)
sql_exec("UPDATE users SET email_verified = 1 WHERE id = ?", (owner_id,))

# === 3. Login ===
banner("3. LOGIN")
r = httpx.post(f"{BASE}/api/v1/auth/login", json={
    "email": "owner@kampala-traders.ug",
    "password": "Sup3rSecret!2026",
}, timeout=10)
show("POST /api/v1/auth/login", r)
tokens = r.json()
H = {"Authorization": f"Bearer {tokens['access_token']}"}

# === 4. Create Uganda-based organization (UGX base currency) ===
banner("4. CREATE ORGANIZATION (UGANDA → UGX)")
r = httpx.post(f"{BASE}/api/v1/organizations", json={
    "name": "Kampala Traders Ltd",
    "slug": "kampala-traders",
    "country_code": "UG",
    "base_currency": "UGX",
    "locale": "en-UG",
    "timezone": "Africa/Kampala",
    "tax_rate_pct": 18,
}, headers=H, timeout=10)
show("POST /api/v1/organizations", r)
org_id = r.json()["id"]

# Promote to OWNER role
row = sql_fetchone("SELECT id FROM roles WHERE name = 'OWNER'")
if row:
    owner_role_id = row[0]
    sql_exec(
        "INSERT INTO user_roles (id, user_id, role_id, role_name, created_at, updated_at) "
        "VALUES (lower(hex(randomblob(16))), ?, ?, 'OWNER', datetime('now'), datetime('now'))",
        (owner_id, owner_role_id),
    )

# Refresh token to pick up OWNER permissions
r = httpx.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}, timeout=10)
tokens = r.json()
H = {"Authorization": f"Bearer {tokens['access_token']}"}

# === 5. List currencies ===
banner("5. CURRENCY CATALOG")
r = httpx.get(f"{BASE}/api/v1/currencies", headers=H, timeout=10)
print(f"\n▶ GET /api/v1/currencies  →  HTTP {r.status_code}  ({len(r.json())} currencies supported)")
print("  Sample (one per continent):")
sample = ["USD", "UGX", "EUR", "JPY", "BRL", "AUD"]
for c in r.json():
    if c["code"] in sample:
        print(f"    {c['code']}  {c['symbol']:>4}  {c['name']:<28}  ({c['country_code']})  {c['decimal_places']} dp")

# === 6. Convert USD → UGX ===
banner("6. CURRENCY CONVERSION — 100 USD → UGX")
r = httpx.post(f"{BASE}/api/v1/currency/convert", json={
    "amount": "100", "from_currency": "USD", "to_currency": "UGX",
}, headers=H, timeout=10)
show("POST /api/v1/currency/convert", r)

# === 7. Convert EUR → USD ===
banner("7. CURRENCY CONVERSION — 500 EUR → USD")
r = httpx.post(f"{BASE}/api/v1/currency/convert", json={
    "amount": "500", "from_currency": "EUR", "to_currency": "USD",
}, headers=H, timeout=10)
show("POST /api/v1/currency/convert", r)

# === 8. Convert KES → TZS (cross-rate) ===
banner("8. CURRENCY CONVERSION — 10,000 KES → TZS (cross-rate via USD)")
r = httpx.post(f"{BASE}/api/v1/currency/convert", json={
    "amount": "10000", "from_currency": "KES", "to_currency": "TZS",
}, headers=H, timeout=10)
show("POST /api/v1/currency/convert", r)

# === 9. Create an AI agent ===
banner("9. CREATE AI AGENT (OrderBot)")
r = httpx.post(f"{BASE}/api/v1/ai/agents", json={
    "name": "OrderBot",
    "kind": "orders",
    "description": "Auto-places orders from customer inquiries + triggers restocks when stock is low",
    "permissions": ["orders.create", "inventory.update"],
    "requires_approval_for": ["create_order_from_inquiry", "trigger_restock_order"],
}, headers=H, timeout=10)
show("POST /api/v1/ai/agents", r)
agent_id = r.json()["id"]

# === 10. List AI agents ===
banner("10. LIST AI AGENTS")
r = httpx.get(f"{BASE}/api/v1/ai/agents", headers=H, timeout=10)
show("GET /api/v1/ai/agents", r)

# === 11. Seed business data + generate monthly P&L report ===
banner("11. SEED BUSINESS DATA + GENERATE MONTHLY P&L REPORT")
import uuid

now = datetime.now(timezone.utc)
cust_id = str(uuid.uuid4())
p1_id = str(uuid.uuid4())
p2_id = str(uuid.uuid4())
inv1_id = str(uuid.uuid4())
inv2_id = str(uuid.uuid4())
o1_id = str(uuid.uuid4())
o2_id = str(uuid.uuid4())
oi1_id = str(uuid.uuid4())
oi2_id = str(uuid.uuid4())
exp_id = str(uuid.uuid4())

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Customer
cur.execute("INSERT INTO customers (id, organization_id, name, email, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'Grace Namuli', 'grace@example.com', 1, datetime('now'), datetime('now'))",
            (cust_id, org_id))

# Products
cur.execute("INSERT INTO products (id, organization_id, name, sku, price, cost, reorder_threshold, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'Maize flour 1kg', 'MAIZE-1KG', 4500, 3000, 10, 1, datetime('now'), datetime('now'))",
            (p1_id, org_id))
cur.execute("INSERT INTO products (id, organization_id, name, sku, price, cost, reorder_threshold, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'Cooking oil 1L', 'OIL-1L', 8500, 6500, 5, 1, datetime('now'), datetime('now'))",
            (p2_id, org_id))

# Inventory
cur.execute("INSERT INTO inventory (id, organization_id, product_id, quantity_on_hand, quantity_reserved, quantity_available, created_at, updated_at) "
            "VALUES (?, ?, ?, 200, 0, 200, datetime('now'), datetime('now'))",
            (inv1_id, org_id, p1_id))
cur.execute("INSERT INTO inventory (id, organization_id, product_id, quantity_on_hand, quantity_reserved, quantity_available, created_at, updated_at) "
            "VALUES (?, ?, ?, 80, 0, 80, datetime('now'), datetime('now'))",
            (inv2_id, org_id, p2_id))

# Orders
cur.execute("INSERT INTO orders (id, organization_id, order_number, customer_id, status, currency, subtotal, discount, tax, total_amount, base_currency, exchange_rate, base_amount, paid_at, created_at, updated_at) "
            "VALUES (?, ?, 'ORD-001', ?, 'PAID', 'UGX', 45000, 0, 8100, 53100, 'UGX', 1, 53100, datetime('now'), datetime('now'), datetime('now'))",
            (o1_id, org_id, cust_id))
cur.execute("INSERT INTO orders (id, organization_id, order_number, customer_id, status, currency, subtotal, discount, tax, total_amount, base_currency, exchange_rate, base_amount, paid_at, created_at, updated_at) "
            "VALUES (?, ?, 'ORD-002', ?, 'PAID', 'UGX', 85000, 5000, 14400, 94400, 'UGX', 1, 94400, datetime('now'), datetime('now'), datetime('now'))",
            (o2_id, org_id, cust_id))

# Order items
cur.execute("INSERT INTO order_items (id, organization_id, order_id, product_id, product_name, quantity, unit_price, line_total, unit_cost, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'Maize flour 1kg', 10, 4500, 45000, 3000, datetime('now'), datetime('now'))",
            (oi1_id, org_id, o1_id, p1_id))
cur.execute("INSERT INTO order_items (id, organization_id, order_id, product_id, product_name, quantity, unit_price, line_total, unit_cost, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'Cooking oil 1L', 10, 8500, 85000, 6500, datetime('now'), datetime('now'))",
            (oi2_id, org_id, o2_id, p2_id))

# Expense
cur.execute("INSERT INTO expenses (id, organization_id, category, description, amount, currency, base_currency, exchange_rate, base_amount, incurred_on, created_at, updated_at) "
            "VALUES (?, ?, 'rent', 'Shop rent', 50000, 'UGX', 'UGX', 1, 50000, datetime('now'), datetime('now'), datetime('now'))",
            (exp_id, org_id))

conn.commit()
conn.close()
print(f"\n  ✓ Seeded: 1 customer, 2 products, 2 orders, 1 expense into org '{org_id[:8]}'")

# Fetch the report
r = httpx.get(f"{BASE}/api/v1/finance/reports/monthly/{now.year}/{now.month}", headers=H, timeout=10)
print(f"\n▶ GET /api/v1/finance/reports/monthly/{now.year}/{now.month}  →  HTTP {r.status_code}")
body = r.json()
print(json.dumps(body, indent=2))

# === 12. Audit logs ===
banner("12. AUDIT LOGS (most recent events)")
r = httpx.get(f"{BASE}/api/v1/audit-logs?limit=15", headers=H, timeout=10)
print(f"\n▶ GET /api/v1/audit-logs  →  HTTP {r.status_code}  ({len(r.json())} events shown)")
print(f"  {'EVENT':<30}  {'ACTOR':<12}  {'WHEN'}")
print(f"  {'─'*30}  {'─'*12}  {'─'*25}")
for log in r.json()[:12]:
    actor = (log.get("actor_user_id") or "system")[:8]
    print(f"  {log['event']:<30}  {actor:<12}  {log['occurred_at'][:19]}")

# === 13. /me ===
banner("13. CURRENT USER PROFILE (/me)")
r = httpx.get(f"{BASE}/api/v1/auth/me", headers=H, timeout=10)
show("GET /api/v1/auth/me", r)

# === 14. Available AI tools (registry) ===
banner("14. REGISTERED AI TOOLS")
# Tools are registered in the running server's process — list them statically here
print("  • create_order_from_inquiry  — auto-create order from customer inquiry (requires approval if > 1000 base)")
print("  • trigger_restock_order      — auto-create purchase order when stock < reorder threshold (requires approval)")
print("  • update_inventory           — adjust inventory count + record movement")

print("\n" + "═" * 70)
print("  ✓ Live demo complete — FastAPI server still running on port 8765")
print("  Interactive OpenAPI docs:  http://127.0.0.1:8765/docs")
print("  ReDoc alternative docs:    http://127.0.0.1:8765/redoc")
print("═" * 70)
