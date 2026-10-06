"""
app/core/deps.py
================
FastAPI dependencies: current user, organization, permission checks,
tenant-scoped DB helpers.
"""
from __future__ import annotations

from typing import Annotated, Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token_of_type, TOKEN_TYPE_ACCESS
from app.db.session import get_db
from app.models.user import User


bearer_scheme = HTTPBearer(auto_error=False)


class TenantContext:
    """Per-request context carrying user, organization, agent info."""

    def __init__(
        self,
        user: Optional[User] = None,
        organization_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self.user = user
        self.organization_id = organization_id
        self.agent_id = agent_id
        self.ip_address = ip_address
        self.user_agent = user_agent

    @property
    def actor_user_id(self) -> Optional[str]:
        return self.user.id if self.user else None

    @property
    def actor_label(self) -> str:
        if self.user:
            return f"user:{self.user.id}"
        if self.agent_id:
            return f"agent:{self.agent_id}"
        return "anonymous"


def _extract_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
) -> User:
    token = (credentials.credentials if credentials else None) or _extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token_of_type(token, TOKEN_TYPE_ACCESS)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload["sub"]
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account inactive or not found")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    # Attach request-scoped context for downstream services
    request.state.tenant_ctx = TenantContext(
        user=user,
        organization_id=user.organization_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    return user


def get_tenant_ctx(request: Request) -> TenantContext:
    ctx: Optional[TenantContext] = getattr(request.state, "tenant_ctx", None)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return ctx


def require_permission(codename: str) -> Callable:
    """Dependency factory: enforces a specific permission codename."""

    def _checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not user.has_permission(codename):
            raise HTTPException(
                status_code=403,
                detail=f"Missing required permission: {codename}",
            )
        return user

    return _checker


def require_any_permission(*codenames: str) -> Callable:
    """At least one of the listed permissions must be present."""

    def _checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.is_superuser:
            return user
        if not any(user.has_permission(c) for c in codenames):
            raise HTTPException(
                status_code=403,
                detail=f"Missing any of required permissions: {', '.join(codenames)}",
            )
        return user

    return _checker


def require_organization_membership(organization_id: str, user: User) -> None:
    """Hard tenant-isolation check."""
    if user.is_superuser:
        return
    if not user.organization_id or user.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")


def get_db_for_user(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Session:
    """DB session annotated with the user's organization context.

    Service-layer queries should always filter by user.organization_id when
    querying tenant-scoped tables.
    """
    return db
