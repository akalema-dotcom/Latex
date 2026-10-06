"""
app/services/ai_agent_service.py
================================
AI agent service — runs tasks, dispatches tool calls, manages approvals.

The AI layer NEVER directly manipulates database tables. It calls tools,
which call services, which talk to the DB.

Sensitive actions require human approval before they are committed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import TenantContext
from app.models.ai_agent import AIAgent, AITask, AIAction, AIApproval
from app.ai.tools.registry import get_tool, list_tools
from app.services.audit_service import AuditService


class AIAgentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit = AuditService(db)

    # ----- Agent management -----
    def create_agent(
        self,
        organization_id: str,
        name: str,
        *,
        kind: str = "general",
        permissions: Optional[list[str]] = None,
        requires_approval_for: Optional[list[str]] = None,
        description: Optional[str] = None,
    ) -> AIAgent:
        agent = AIAgent(
            organization_id=organization_id,
            name=name,
            kind=kind,
            description=description,
            permissions=permissions or [],
            requires_approval_for=requires_approval_for or [],
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    # ----- Task execution -----
    def submit_task(
        self,
        agent_id: str,
        objective: str,
        input_data: dict,
        ctx: TenantContext,
    ) -> AITask:
        agent = self.db.get(AIAgent, agent_id)
        if not agent or agent.organization_id != ctx.organization_id:
            raise ValueError("Agent not found in this organization")

        task = AITask(
            organization_id=ctx.organization_id,
            agent_id=agent.id,
            triggered_by_user_id=ctx.actor_user_id,
            objective=objective,
            input=input_data,
            status="PENDING",
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def run_task(self, task_id: str, ctx: TenantContext) -> AITask:
        task = self.db.get(AITask, task_id)
        if not task or task.organization_id != ctx.organization_id:
            raise ValueError("Task not found")

        task.status = "RUNNING"
        task.started_at = datetime.now(timezone.utc)
        self.db.commit()

        # Naive execution: each step in the input["steps"] list invokes a tool.
        steps = task.input.get("steps", [])
        outputs = []
        for step in steps:
            tool_name = step.get("tool")
            params = step.get("parameters", {})
            tool = get_tool(tool_name) if tool_name else None
            if not tool:
                task.status = "FAILED"
                task.error = f"Unknown tool: {tool_name}"
                self.db.commit()
                return task

            action = AIAction(
                organization_id=ctx.organization_id,
                task_id=task.id,
                agent_id=task.agent_id,
                user_id=ctx.actor_user_id,
                tool=tool.name,
                parameters=params,
                status="STARTED",
                started_at=datetime.now(timezone.utc),
                requires_approval=tool.requires_approval,
            )
            self.db.add(action)
            self.db.flush()

            self.audit.log(
                event="AI_ACTION_STARTED",
                organization_id=ctx.organization_id,
                actor_user_id=ctx.actor_user_id,
                actor_agent_id=task.agent_id,
                target_type="ai_action",
                target_id=action.id,
                details={"tool": tool.name, "parameters": params},
            )

            if tool.requires_approval:
                approval = AIApproval(
                    organization_id=ctx.organization_id,
                    task_id=task.id,
                    requested_action_id=action.id,
                    requested_by_agent_id=task.agent_id,
                    requested_by_user_id=ctx.actor_user_id,
                    description=f"Approval required for tool: {tool.name}",
                    payload=params,
                    status="PENDING",
                )
                self.db.add(approval)
                action.approval_id = approval.id
                task.status = "AWAITING_APPROVAL"
                self.db.commit()
                outputs.append({"action_id": action.id, "status": "awaiting_approval"})
                # In production, the orchestrator would pause here.
                # For demo, we mark and stop.
                return task

            # Run synchronously
            try:
                result = tool.execute(self.db, ctx, params)
                action.result = result.output
                action.status = "SUCCESS" if result.success else "FAILED"
                action.error = result.error
                action.completed_at = datetime.now(timezone.utc)
                outputs.append({"action_id": action.id, "result": result.output, "success": result.success})
            except Exception as exc:
                action.status = "FAILED"
                action.error = str(exc)
                action.completed_at = datetime.now(timezone.utc)
                task.status = "FAILED"
                task.error = str(exc)
                self.db.commit()
                return task

        task.output = {"steps": outputs}
        task.status = "COMPLETED"
        task.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        return task

    # ----- Approvals -----
    def approve_action(self, approval_id: str, user_id: str, notes: Optional[str] = None) -> AIApproval:
        approval = self.db.get(AIApproval, approval_id)
        if not approval:
            raise ValueError("Approval not found")
        if approval.status != "PENDING":
            raise ValueError(f"Approval already {approval.status}")
        approval.status = "APPROVED"
        approval.decided_by_user_id = user_id
        approval.decided_at = datetime.now(timezone.utc)
        approval.decision_notes = notes
        self.audit.log(
            event="AI_APPROVAL_APPROVED",
            organization_id=approval.organization_id,
            actor_user_id=user_id,
            target_type="ai_approval",
            target_id=approval.id,
        )
        self.db.commit()
        return approval

    def reject_action(self, approval_id: str, user_id: str, notes: Optional[str] = None) -> AIApproval:
        approval = self.db.get(AIApproval, approval_id)
        if not approval:
            raise ValueError("Approval not found")
        if approval.status != "PENDING":
            raise ValueError(f"Approval already {approval.status}")
        approval.status = "REJECTED"
        approval.decided_by_user_id = user_id
        approval.decided_at = datetime.now(timezone.utc)
        approval.decision_notes = notes
        self.audit.log(
            event="AI_APPROVAL_REJECTED",
            organization_id=approval.organization_id,
            actor_user_id=user_id,
            target_type="ai_approval",
            target_id=approval.id,
        )
        self.db.commit()
        return approval
