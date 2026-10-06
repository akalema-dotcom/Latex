"""
app/services/auth_service.py
============================
Authentication service: registration, login, refresh, logout, email
verification, password reset, session management.

CRITICAL:
- passwords are hashed with bcrypt (never plaintext)
- access tokens are short-lived
- refresh tokens are longer-lived, rotated, and revocable
- failed login attempts are tracked (lockout after N)
- secrets are NEVER returned in API responses
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token, create_refresh_token, create_email_verification_token,
    create_password_reset_token, decode_token_of_type, hash_password, verify_password,
    TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH, TOKEN_TYPE_EMAIL_VERIFY, TOKEN_TYPE_PASSWORD_RESET,
)
from app.db.session import SessionLocal
from app.integrations.email.service import email_service
from app.models.email_verification import EmailVerificationToken
from app.models.password_reset import PasswordResetToken
from app.models.user import User, Session as UserSession, Role, Permission, UserRole, ROLE_PERMISSIONS
from app.services.audit_service import AuditService
from app.utils.timezone import ensure_aware, is_past, now_utc


# --- constants --------------------------------------------------------------
FAILED_LOGIN_LOCKOUT_THRESHOLD = 5
FAILED_LOGIN_LOCKOUT_MINUTES = 15


# --- exceptions -------------------------------------------------------------
class AuthError(Exception):
    """Base class for all auth-related business errors."""

    code: str = "auth_error"
    http_status: int = 400


class EmailAlreadyRegistered(AuthError):
    code = "email_already_registered"
    http_status = 409


class InvalidCredentials(AuthError):
    code = "invalid_credentials"
    http_status = 401


class AccountLocked(AuthError):
    code = "account_locked"
    http_status = 423


class AccountDeactivated(AuthError):
    code = "account_deactivated"
    http_status = 403


class EmailNotVerified(AuthError):
    code = "email_not_verified"
    http_status = 403


class TokenInvalid(AuthError):
    code = "token_invalid"
    http_status = 401


class TokenExpired(AuthError):
    code = "token_expired"
    http_status = 401


class SessionRevoked(AuthError):
    code = "session_revoked"
    http_status = 401


# --- helpers ----------------------------------------------------------------
def _hash_token(token: str) -> str:
    """SHA-256 hash of a token — only the hash is stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _seed_default_roles(db: Session) -> None:
    """Idempotently seed the canonical roles + permissions."""
    # Permissions
    from app.models.user import PERMISSION_CATALOG
    existing_perms = {p.codename: p for p in db.execute(select(Permission)).scalars()}
    for code in PERMISSION_CATALOG:
        if code not in existing_perms:
            p = Permission(codename=code, description=code)
            db.add(p)
            existing_perms[code] = p
    db.flush()

    # Roles
    existing_roles = {r.name: r for r in db.execute(select(Role)).scalars()}
    for role_name, perm_codes in ROLE_PERMISSIONS.items():
        if role_name not in existing_roles:
            role = Role(name=role_name, description=f"{role_name} role")
            db.add(role)
            db.flush()
            existing_roles[role_name] = role
        role = existing_roles[role_name]
        wanted_perm_ids = {existing_perms[c].id for c in perm_codes if c in existing_perms}
        current_perm_ids = {p.id for p in role.permissions}
        if wanted_perm_ids != current_perm_ids:
            role.permissions = [existing_perms[c] for c in perm_codes if c in existing_perms]
    db.flush()


# --- service ---------------------------------------------------------------
class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit = AuditService(db)

    # ----- Registration -----
    def register(
        self,
        *,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        organization_id: Optional[str] = None,
        auto_verify: bool = False,
    ) -> User:
        email = email.lower().strip()
        existing = self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            raise EmailAlreadyRegistered("Email is already registered")

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            organization_id=organization_id,
            email_verified=auto_verify,
        )
        self.db.add(user)
        self.db.flush()

        # Assign default VIEWER role (callers can promote later)
        viewer = self.db.execute(select(Role).where(Role.name == "VIEWER")).scalar_one_or_none()
        if viewer:
            self.db.add(UserRole(user_id=user.id, role_id=viewer.id, role_name="VIEWER"))
            self.db.flush()

        # Generate email verification token
        token = create_email_verification_token(user.id)
        record = EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(user)

        # Send verification email (no-op in dev / tests)
        try:
            email_service.send_email_verification(user.email, token)
        except Exception:
            pass

        self.audit.log(
            event="USER_REGISTERED",
            organization_id=organization_id,
            actor_user_id=user.id,
            target_type="user",
            target_id=user.id,
        )
        self.db.commit()
        return user

    # ----- Login -----
    def login(
        self,
        email: str,
        password: str,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple[User, str, str, str]:
        """Return (user, access_token, refresh_token, session_id)."""
        email = email.lower().strip()
        user = self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user:
            raise InvalidCredentials("Invalid credentials")

        # Lockout check
        if user.locked_until and not is_past(user.locked_until):
            raise AccountLocked("Account temporarily locked")

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= FAILED_LOGIN_LOCKOUT_THRESHOLD:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=FAILED_LOGIN_LOCKOUT_MINUTES)
            self.db.commit()
            raise InvalidCredentials("Invalid credentials")

        if not user.is_active:
            raise AccountDeactivated("Account is deactivated")

        # Successful login — reset counters
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)

        # Create session
        session_id = secrets.token_urlsafe(16)
        refresh_token = create_refresh_token(user.id, session_id)
        session = UserSession(
            id=session_id,
            user_id=user.id,
            organization_id=user.organization_id,
            refresh_token_jti=_hash_token(refresh_token),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(session)

        # Access token
        roles = user.roles
        permissions = sorted(user.permissions)
        access_token = create_access_token(
            user_id=user.id,
            organization_id=user.organization_id,
            roles=roles,
            scopes=permissions,
        )

        self.audit.log(
            event="USER_LOGIN",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            target_type="user",
            target_id=user.id,
        )
        self.db.commit()

        # Best-effort login notification
        try:
            if ip_address:
                email_service.send_login_notification(user.email, ip_address, user_agent or "")
        except Exception:
            pass

        return user, access_token, refresh_token, session_id

    # ----- Refresh -----
    def refresh(self, refresh_token: str) -> tuple[str, str, str]:
        """Rotate refresh token. Returns (new_access, new_refresh, session_id)."""
        payload = decode_token_of_type(refresh_token, TOKEN_TYPE_REFRESH)
        if not payload:
            raise TokenInvalid("Invalid refresh token")

        user_id = payload["sub"]
        jti_hash = _hash_token(refresh_token)
        session = self.db.execute(
            select(UserSession).where(UserSession.refresh_token_jti == jti_hash)
        ).scalar_one_or_none()

        if not session or session.is_revoked() or session.is_expired():
            raise SessionRevoked("Session is revoked or expired")

        user = self.db.get(User, user_id)
        if not user or not user.is_active:
            raise AccountDeactivated("Account is deactivated")

        # Rotate: revoke old, issue new
        session.revoked_at = datetime.now(timezone.utc)
        new_session_id = secrets.token_urlsafe(16)
        new_refresh = create_refresh_token(user.id, new_session_id)
        new_session = UserSession(
            id=new_session_id,
            user_id=user.id,
            organization_id=user.organization_id,
            refresh_token_jti=_hash_token(new_refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(new_session)

        roles = user.roles
        permissions = sorted(user.permissions)
        new_access = create_access_token(
            user_id=user.id,
            organization_id=user.organization_id,
            roles=roles,
            scopes=permissions,
        )

        self.db.commit()
        return new_access, new_refresh, new_session_id

    # ----- Logout -----
    def logout(self, refresh_token: str) -> None:
        payload = decode_token_of_type(refresh_token, TOKEN_TYPE_REFRESH)
        if not payload:
            return  # idempotent
        jti_hash = _hash_token(refresh_token)
        session = self.db.execute(
            select(UserSession).where(UserSession.refresh_token_jti == jti_hash)
        ).scalar_one_or_none()
        if session and not session.is_revoked():
            session.revoked_at = datetime.now(timezone.utc)
            self.audit.log(
                event="USER_LOGOUT",
                organization_id=session.organization_id,
                actor_user_id=session.user_id,
            )
            self.db.commit()

    # ----- Email verification -----
    def verify_email(self, token: str) -> User:
        payload = decode_token_of_type(token, TOKEN_TYPE_EMAIL_VERIFY)
        if not payload:
            raise TokenExpired("Token invalid or expired")
        user_id = payload["sub"]
        record = self.db.execute(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.token_hash == _hash_token(token))
        ).scalar_one_or_none()
        if not record or record.is_used:
            raise TokenInvalid("Token already used or invalid")
        if is_past(record.expires_at):
            raise TokenExpired("Token expired")

        user = self.db.get(User, user_id)
        if not user:
            raise TokenInvalid("User not found")
        user.email_verified = True
        record.is_used = True
        record.used_at = now_utc()
        self.audit.log(
            event="EMAIL_VERIFIED",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            target_type="user",
            target_id=user.id,
        )
        self.db.commit()
        return user

    # ----- Password reset flow -----
    def request_password_reset(self, email: str) -> None:
        """Always returns None — never reveals whether the email exists."""
        email = email.lower().strip()
        user = self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user:
            return
        token = create_password_reset_token(user.id)
        record = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
        self.db.add(record)
        self.db.commit()
        try:
            email_service.send_password_reset(user.email, token)
        except Exception:
            pass

    def reset_password(self, token: str, new_password: str) -> User:
        payload = decode_token_of_type(token, TOKEN_TYPE_PASSWORD_RESET)
        if not payload:
            raise TokenExpired("Token invalid or expired")
        record = self.db.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == _hash_token(token))
        ).scalar_one_or_none()
        if not record or record.is_used:
            raise TokenInvalid("Token already used or invalid")
        if is_past(record.expires_at):
            raise TokenExpired("Token expired")

        user = self.db.get(User, record.user_id)
        if not user:
            raise TokenInvalid("User not found")
        user.password_hash = hash_password(new_password)
        record.is_used = True
        record.used_at = now_utc()

        # Revoke all sessions for security
        for s in user.sessions:
            s.revoked_at = datetime.now(timezone.utc)

        self.audit.log(
            event="PASSWORD_RESET",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            target_type="user",
            target_id=user.id,
        )
        self.db.commit()
        return user

    # ----- Change password (authenticated) -----
    def change_password(self, user_id: str, current_password: str, new_password: str) -> User:
        user = self.db.get(User, user_id)
        if not user:
            raise InvalidCredentials("User not found")
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentials("Current password is incorrect")
        user.password_hash = hash_password(new_password)
        self.audit.log(
            event="PASSWORD_CHANGED",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            target_type="user",
            target_id=user.id,
        )
        self.db.commit()
        return user

    # ----- Sessions -----
    def list_sessions(self, user_id: str) -> list[UserSession]:
        return list(self.db.execute(
            select(UserSession).where(UserSession.user_id == user_id).order_by(UserSession.created_at.desc())
        ).scalars())

    def revoke_session(self, user_id: str, session_id: str) -> None:
        s = self.db.get(UserSession, session_id)
        if not s or s.user_id != user_id:
            raise TokenInvalid("Session not found")
        s.revoked_at = datetime.now(timezone.utc)
        self.audit.log(
            event="SESSION_REVOKED",
            organization_id=s.organization_id,
            actor_user_id=user_id,
            target_type="session",
            target_id=s.id,
        )
        self.db.commit()

    # ----- Account deactivation/reactivation -----
    def deactivate(self, user_id: str) -> None:
        user = self.db.get(User, user_id)
        if not user:
            raise InvalidCredentials("User not found")
        user.is_active = False
        for s in user.sessions:
            s.revoked_at = datetime.now(timezone.utc)
        self.db.commit()

    def reactivate(self, user_id: str) -> None:
        user = self.db.get(User, user_id)
        if not user:
            raise InvalidCredentials("User not found")
        user.is_active = True
        self.db.commit()
