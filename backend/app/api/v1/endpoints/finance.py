"""
app/api/v1/endpoints/finance.py
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permission
from app.models.user import User
from app.services.finance_service import FinanceService

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/reports/profit-loss")
def get_profit_loss(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("reports.read"))],
    year: int = Query(...),
    month: int | None = Query(default=None, ge=1, le=12),
):
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    svc = FinanceService(db)
    if month is None:
        return svc.yearly_report(user.organization_id, year).to_dict()
    return svc.monthly_report(user.organization_id, year, month).to_dict()


@router.get("/reports/monthly/{year}/{month}")
def get_monthly_report(
    year: int,
    month: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("reports.read"))],
):
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    svc = FinanceService(db)
    return svc.monthly_report(user.organization_id, year, month).to_dict()


@router.get("/reports/yearly/{year}")
def get_yearly_report(
    year: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("reports.read"))],
):
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    svc = FinanceService(db)
    return svc.yearly_report(user.organization_id, year).to_dict()
