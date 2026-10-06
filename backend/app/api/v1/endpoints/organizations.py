"""
app/api/v1/endpoints/organizations.py
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.currency_catalog import is_valid_currency_code
from app.core.deps import get_current_user, get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationOut, OrganizationUpdate
from app.services.audit_service import AuditService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if not is_valid_currency_code(payload.base_currency):
        raise HTTPException(status_code=422, detail=f"Invalid currency code: {payload.base_currency}")
    if user.organization_id:
        raise HTTPException(status_code=400, detail="User already belongs to an organization")

    slug_taken = db.execute(select(Organization).where(Organization.slug == payload.slug)).scalar_one_or_none()
    if slug_taken:
        raise HTTPException(status_code=409, detail="Slug already taken")

    org = Organization(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        country_code=payload.country_code.upper(),
        base_currency=payload.base_currency.upper(),
        locale=payload.locale,
        timezone=payload.timezone,
        tax_rate_pct=payload.tax_rate_pct,
    )
    db.add(org)
    db.flush()
    user.organization_id = org.id
    AuditService(db).log(
        event="ORGANIZATION_CREATED",
        organization_id=org.id,
        actor_user_id=user.id,
        target_type="organization",
        target_id=org.id,
    )
    db.commit()
    db.refresh(org)
    return org


@router.get("/me", response_model=OrganizationOut)
def get_my_organization(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="User does not belong to an organization")
    org = db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/me", response_model=OrganizationOut)
def update_my_organization(
    payload: OrganizationUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="User has no organization")
    if not user.has_permission("settings.manage"):
        raise HTTPException(status_code=403, detail="Missing permission: settings.manage")
    org = db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    data = payload.model_dump(exclude_unset=True)
    if "base_currency" in data and data["base_currency"]:
        if not is_valid_currency_code(data["base_currency"]):
            raise HTTPException(status_code=422, detail="Invalid currency code")
        data["base_currency"] = data["base_currency"].upper()
    if "country_code" in data and data["country_code"]:
        data["country_code"] = data["country_code"].upper()
    for k, v in data.items():
        setattr(org, k, v)
    AuditService(db).log(
        event="ORGANIZATION_UPDATED",
        organization_id=org.id,
        actor_user_id=user.id,
        target_type="organization",
        target_id=org.id,
        details=data,
    )
    db.commit()
    db.refresh(org)
    return org
