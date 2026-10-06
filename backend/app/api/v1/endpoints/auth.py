"""
app/api/v1/endpoints/auth.py
============================
Authentication endpoints.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordIn, EmailVerifyIn, PasswordResetIn, PasswordResetRequestIn,
    SessionOut, TokenOut, TokenRefresh, UserLogin, UserOut, UserRegister,
)
from app.services.auth_service import (
    AuthService, AuthError, EmailAlreadyRegistered, InvalidCredentials,
    AccountLocked, AccountDeactivated, TokenInvalid, TokenExpired,
    _seed_default_roles,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _map_auth_error(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.code)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Annotated[Session, Depends(get_db)]):
    _seed_default_roles(db)
    svc = AuthService(db)
    try:
        user = svc.register(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            organization_id=payload.organization_id,
        )
    except EmailAlreadyRegistered as exc:
        raise _map_auth_error(exc) from exc
    return user


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, request: Request, db: Annotated[Session, Depends(get_db)]):
    svc = AuthService(db)
    try:
        user, access, refresh, sid = svc.login(
            email=payload.email,
            password=payload.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except (InvalidCredentials, AccountLocked, AccountDeactivated) as exc:
        raise _map_auth_error(exc) from exc
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        session_id=sid,
    )


@router.post("/refresh", response_model=TokenOut)
def refresh(payload: TokenRefresh, db: Annotated[Session, Depends(get_db)]):
    svc = AuthService(db)
    try:
        access, refresh_new, sid = svc.refresh(payload.refresh_token)
    except (TokenInvalid, TokenExpired) as exc:
        raise _map_auth_error(exc) from exc
    return TokenOut(
        access_token=access,
        refresh_token=refresh_new,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        session_id=sid,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: TokenRefresh, db: Annotated[Session, Depends(get_db)]):
    svc = AuthService(db)
    svc.logout(payload.refresh_token)
    return None


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)]):
    return user


@router.post("/verify-email", response_model=UserOut)
def verify_email(payload: EmailVerifyIn, db: Annotated[Session, Depends(get_db)]):
    svc = AuthService(db)
    try:
        return svc.verify_email(payload.token)
    except (TokenInvalid, TokenExpired) as exc:
        raise _map_auth_error(exc) from exc


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(payload: PasswordResetRequestIn, db: Annotated[Session, Depends(get_db)]):
    svc = AuthService(db)
    svc.request_password_reset(payload.email)
    return None


@router.post("/reset-password", response_model=UserOut)
def reset_password(payload: PasswordResetIn, db: Annotated[Session, Depends(get_db)]):
    svc = AuthService(db)
    try:
        return svc.reset_password(payload.token, payload.new_password)
    except (TokenInvalid, TokenExpired) as exc:
        raise _map_auth_error(exc) from exc


@router.post("/change-password", response_model=UserOut)
def change_password(
    payload: ChangePasswordIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = AuthService(db)
    try:
        return svc.change_password(user.id, payload.current_password, payload.new_password)
    except InvalidCredentials as exc:
        raise _map_auth_error(exc) from exc


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = AuthService(db)
    return svc.list_sessions(user.id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = AuthService(db)
    try:
        svc.revoke_session(user.id, session_id)
    except TokenInvalid as exc:
        raise _map_auth_error(exc) from exc
    return None
