"""
app/ai/tools/base.py
====================
AI tool abstraction.

AI agents NEVER directly manipulate database tables. They invoke tools,
which themselves call services. This indirection enforces:
- organization isolation
- user permissions
- audit logging
- approval requirements for sensitive actions
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.deps import TenantContext
from app.services.audit_service import AuditService


@dataclass
class ToolResult:
    success: bool
    output: dict
    error: Optional[str] = None
    requires_approval: bool = False


class AITool(ABC):
    """Every AI tool implements this interface."""

    name: str = "abstract_tool"
    requires_approval: bool = False
    required_permission: str = ""

    @abstractmethod
    def execute(self, db: Session, ctx: TenantContext, parameters: dict) -> ToolResult:
        """Run the tool. Must enforce tenant isolation + permission check."""
        raise NotImplementedError

    def _check_permission(self, ctx: TenantContext) -> bool:
        if not ctx.user:
            return False
        if ctx.user.is_superuser:
            return True
        return ctx.user.has_permission(self.required_permission)

    def _audit(self, db: Session, ctx: TenantContext, parameters: dict, result: ToolResult) -> None:
        AuditService(db).log(
            event="AI_ACTION_COMPLETED" if result.success else "AI_ACTION_FAILED",
            organization_id=ctx.organization_id,
            actor_user_id=ctx.actor_user_id,
            actor_agent_id=ctx.agent_id,
            target_type="ai_tool",
            target_id=self.name,
            details={"parameters": parameters, "success": result.success, "error": result.error},
        )
