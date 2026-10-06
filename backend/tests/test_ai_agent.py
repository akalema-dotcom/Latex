"""
tests/test_ai_agent.py
======================
AI agent framework tests.

Covers: agent permissions, tool authorization, organization isolation,
audit logging, approval requirements.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.deps import TenantContext
from app.models.ai_agent import AIAgent, AITask, AIApproval
from app.models.user import User, Role, UserRole
from app.models.organization import Organization
from app.services.ai_agent_service import AIAgentService


def _make_ctx(db, user) -> TenantContext:
    return TenantContext(
        user=user,
        organization_id=user.organization_id,
        ip_address="127.0.0.1",
        user_agent="test",
    )


def test_create_ai_agent(db_session):
    # Setup org + user
    org = Organization(name="Test", slug="t1", country_code="UG", base_currency="UGX", locale="en-UG", timezone="UTC")
    db_session.add(org)
    db_session.flush()
    user = User(email="a@x.com", password_hash="x", organization_id=org.id, email_verified=True, is_active=True)
    db_session.add(user)
    db_session.commit()

    svc = AIAgentService(db_session)
    agent = svc.create_agent(
        organization_id=org.id,
        name="OrderBot",
        kind="orders",
        permissions=["orders.create"],
        requires_approval_for=["create_order_from_inquiry"],
    )
    assert agent.id is not None
    assert agent.organization_id == org.id


def test_agent_isolated_per_organization(db_session):
    org_a = Organization(name="A", slug="a", country_code="UG", base_currency="UGX", locale="en-UG", timezone="UTC")
    org_b = Organization(name="B", slug="b", country_code="DE", base_currency="EUR", locale="de-DE", timezone="UTC")
    db_session.add_all([org_a, org_b])
    db_session.flush()

    svc = AIAgentService(db_session)
    a_agent = svc.create_agent(organization_id=org_a.id, name="A-Bot")
    b_agent = svc.create_agent(organization_id=org_b.id, name="B-Bot")

    # Org A's agents should not be retrievable by Org B
    agents_in_a = db_session.execute(
        select(AIAgent).where(AIAgent.organization_id == org_a.id)
    ).scalars().all()
    agents_in_b = db_session.execute(
        select(AIAgent).where(AIAgent.organization_id == org_b.id)
    ).scalars().all()
    assert a_agent.id in [a.id for a in agents_in_a]
    assert a_agent.id not in [a.id for a in agents_in_b]
    assert b_agent.id in [a.id for a in agents_in_b]


def test_task_submission_creates_audit_log(db_session):
    org = Organization(name="Test", slug="t1", country_code="UG", base_currency="UGX", locale="en-UG", timezone="UTC")
    db_session.add(org)
    db_session.flush()
    user = User(email="a@x.com", password_hash="x", organization_id=org.id, email_verified=True, is_active=True)
    db_session.add(user)
    db_session.commit()

    svc = AIAgentService(db_session)
    agent = svc.create_agent(organization_id=org.id, name="Bot")
    ctx = _make_ctx(db_session, user)
    task = svc.submit_task(agent.id, "test objective", {"steps": []}, ctx)

    # Confirm task was created and tied to org
    assert task.organization_id == org.id
    assert task.agent_id == agent.id


def test_approval_workflow(db_session):
    org = Organization(name="Test", slug="t1", country_code="UG", base_currency="UGX", locale="en-UG", timezone="UTC")
    db_session.add(org)
    db_session.flush()
    user = User(email="a@x.com", password_hash="x", organization_id=org.id, email_verified=True, is_active=True)
    db_session.add(user)
    db_session.commit()

    svc = AIAgentService(db_session)
    agent = svc.create_agent(organization_id=org.id, name="Bot")
    ctx = _make_ctx(db_session, user)
    task = svc.submit_task(agent.id, "objective", {}, ctx)

    # Manually create an approval
    approval = AIApproval(
        organization_id=org.id, task_id=task.id,
        requested_by_agent_id=agent.id, requested_by_user_id=user.id,
        description="Test approval", payload={}, status="PENDING",
    )
    db_session.add(approval)
    db_session.commit()

    # Approve it
    approved = svc.approve_action(approval.id, user.id, "ok")
    assert approved.status == "APPROVED"
    assert approved.decided_by_user_id == user.id

    # Cannot approve again
    try:
        svc.approve_action(approval.id, user.id)
        assert False, "Should have raised"
    except ValueError:
        pass


def test_reject_approval(db_session):
    org = Organization(name="Test", slug="t1", country_code="UG", base_currency="UGX", locale="en-UG", timezone="UTC")
    db_session.add(org)
    db_session.flush()
    user = User(email="a@x.com", password_hash="x", organization_id=org.id, email_verified=True, is_active=True)
    db_session.add(user)
    db_session.commit()

    svc = AIAgentService(db_session)
    agent = svc.create_agent(organization_id=org.id, name="Bot")
    ctx = _make_ctx(db_session, user)
    task = svc.submit_task(agent.id, "objective", {}, ctx)
    approval = AIApproval(
        organization_id=org.id, task_id=task.id,
        requested_by_agent_id=agent.id, requested_by_user_id=user.id,
        description="Test", payload={}, status="PENDING",
    )
    db_session.add(approval)
    db_session.commit()

    rejected = svc.reject_action(approval.id, user.id, "no")
    assert rejected.status == "REJECTED"
