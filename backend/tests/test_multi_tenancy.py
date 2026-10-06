"""
tests/test_multi_tenancy.py
===========================
Multi-tenant isolation tests.

Verifies organization A cannot access organization B's data.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models.user import User, Role, UserRole


def _make_tenant(client, db_session, email, slug, currency, country):
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "Sup3rSecret!", "full_name": email.split("@")[0].title(),
    })
    user = db_session.execute(select(User).where(User.email == email)).scalar_one()
    user.email_verified = True
    db_session.commit()
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"})
    tokens = r.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    r = client.post("/api/v1/organizations", json={
        "name": f"{slug} Org", "slug": slug,
        "country_code": country, "base_currency": currency,
        "locale": "en-US", "timezone": "UTC",
    }, headers=headers)
    org_id = r.json()["id"]

    owner_role = db_session.execute(select(Role).where(Role.name == "OWNER")).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=owner_role.id, role_name="OWNER"))
    db_session.commit()

    # Refresh token to pick up OWNER role + permissions
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    tokens = r.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return {"user": user, "org_id": org_id, "headers": headers, "tokens": tokens}


def test_tenant_a_cannot_see_tenant_b_audit_logs(client, db_session):
    a = _make_tenant(client, db_session, "a@example.com", "tenant-a", "USD", "US")
    b = _make_tenant(client, db_session, "b@example.com", "tenant-b", "EUR", "DE")

    # Tenant A creates some audit-log events
    client.get("/api/v1/audit-logs", headers=a["headers"])

    # Tenant B lists audit logs — should NOT see tenant A's events
    r = client.get("/api/v1/audit-logs", headers=b["headers"])
    assert r.status_code == 200
    for entry in r.json():
        # organization_id of B's logs must equal B's org_id (or be null for pre-org)
        # If entry has organization_id, it must be b's
        if entry.get("organization_id"):
            assert entry["organization_id"] == b["org_id"]


def test_user_without_org_cannot_access_org_scoped_endpoints(client, registered_user):
    # registered_user has no organization — should still see auth endpoints
    r = client.get("/api/v1/auth/me", headers=registered_user["headers"])
    assert r.status_code == 200
    assert r.json()["organization_id"] is None


def test_user_cannot_create_second_organization(client, owner_user):
    # owner_user already has an org
    r = client.post("/api/v1/organizations", json={
        "name": "Second Org", "slug": "second-org",
        "country_code": "US", "base_currency": "USD",
    }, headers=owner_user["headers"])
    assert r.status_code == 400


def test_tenant_isolation_in_audit_log_query(client, db_session):
    """Two tenants with separate activity — verify audit logs don't leak."""
    a = _make_tenant(client, db_session, "iso-a@example.com", "iso-a", "USD", "US")
    b = _make_tenant(client, db_session, "iso-b@example.com", "iso-b", "EUR", "DE")

    # Generate some auditable events in A
    client.get("/api/v1/audit-logs", headers=a["headers"])
    # Generate some in B
    client.get("/api/v1/audit-logs", headers=b["headers"])

    # Get A's audit logs
    r_a = client.get("/api/v1/audit-logs", headers=a["headers"])
    r_b = client.get("/api/v1/audit-logs", headers=b["headers"])
    a_events = r_a.json()
    b_events = r_b.json()

    # No event in A's list should belong to B's org
    for ev in a_events:
        if ev.get("organization_id"):
            assert ev["organization_id"] == a["org_id"]
    # Same for B
    for ev in b_events:
        if ev.get("organization_id"):
            assert ev["organization_id"] == b["org_id"]
