"""
app/api/v1/endpoints/ai_agents.py
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_tenant_ctx, require_permission, TenantContext
from app.models.ai_agent import AIAgent, AITask, AIApproval
from app.models.user import User
from app.services.ai_agent_service import AIAgentService

router = APIRouter(prefix="/ai", tags=["ai"])


class AgentCreateIn(BaseModel):
    name: str
    kind: str = "general"
    description: Optional[str] = None
    permissions: list[str] = []
    requires_approval_for: list[str] = []


class TaskSubmitIn(BaseModel):
    agent_id: str
    objective: str
    input: dict = {}
    run: bool = False


class ApprovalDecisionIn(BaseModel):
    decision: str  # "approve" | "reject"
    notes: Optional[str] = None


@router.get("/agents")
def list_agents(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("ai.execute"))],
):
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    agents = db.execute(
        select(AIAgent).where(AIAgent.organization_id == user.organization_id)
    ).scalars().all()
    return [
        {
            "id": a.id, "name": a.name, "kind": a.kind, "status": a.status,
            "permissions": a.permissions, "requires_approval_for": a.requires_approval_for,
            "created_at": a.created_at,
        }
        for a in agents
    ]


@router.post("/agents")
def create_agent(
    payload: AgentCreateIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("settings.manage"))],
    ctx: Annotated[TenantContext, Depends(get_tenant_ctx)],
):
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    svc = AIAgentService(db)
    agent = svc.create_agent(
        organization_id=user.organization_id,
        name=payload.name,
        kind=payload.kind,
        description=payload.description,
        permissions=payload.permissions,
        requires_approval_for=payload.requires_approval_for,
    )
    return {"id": agent.id, "name": agent.name, "status": agent.status}


@router.post("/tasks")
def submit_task(
    payload: TaskSubmitIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("ai.execute"))],
    ctx: Annotated[TenantContext, Depends(get_tenant_ctx)],
):
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    svc = AIAgentService(db)
    task = svc.submit_task(payload.agent_id, payload.objective, payload.input, ctx)
    if payload.run:
        task = svc.run_task(task.id, ctx)
    return {
        "id": task.id,
        "status": task.status,
        "output": task.output,
        "error": task.error,
    }


@router.get("/tasks/{task_id}")
def get_task(
    task_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("ai.execute"))],
):
    task = db.get(AITask, task_id)
    if not task or task.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "agent_id": task.agent_id,
        "objective": task.objective,
        "status": task.status,
        "input": task.input,
        "output": task.output,
        "error": task.error,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


@router.get("/approvals/pending")
def list_pending_approvals(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("ai.approve"))],
):
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    approvals = db.execute(
        select(AIApproval)
        .where(AIApproval.organization_id == user.organization_id)
        .where(AIApproval.status == "PENDING")
        .order_by(AIApproval.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": a.id, "task_id": a.task_id, "description": a.description,
            "payload": a.payload, "status": a.status, "created_at": a.created_at,
        }
        for a in approvals
    ]


@router.post("/approvals/{approval_id}/decide")
def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("ai.approve"))],
):
    svc = AIAgentService(db)
    try:
        if payload.decision == "approve":
            approval = svc.approve_action(approval_id, user.id, payload.notes)
        elif payload.decision == "reject":
            approval = svc.reject_action(approval_id, user.id, payload.notes)
        else:
            raise HTTPException(status_code=400, detail="Invalid decision")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": approval.id, "status": approval.status}
