"""
app/models/user.py
==================
User, Role, Permission, UserRole, Session.

RBAC is permission-based: roles are just bundles of permissions. Every
sensitive endpoint checks a permission, never a role name.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, String, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import UUIDPkMixin, TimestampMixin


# --- Permission catalog -----------------------------------------------------
PERMISSION_CATALOG: list[str] = [
    # Users
    "users.read", "users.create", "users.update", "users.delete",
    # Products
    "products.read", "products.create", "products.update", "products.delete",
    # Orders
    "orders.read", "orders.create", "orders.update", "orders.cancel",
    # Inventory
    "inventory.read", "inventory.update",
    # Finance
    "finance.read", "finance.manage",
    # Expenses
    "expenses.read", "expenses.create", "expenses.update", "expenses.delete",
    # Reports
    "reports.read",
    # AI
    "ai.execute", "ai.approve",
    # Settings
    "settings.manage",
    # Customers
    "customers.read", "customers.create", "customers.update", "customers.delete",
    # Suppliers
    "suppliers.read", "suppliers.create", "suppliers.update", "suppliers.delete",
    # Channels / messaging
    "channels.read", "channels.send",
]


# Default role → permission bundle mapping. Used by the seed migration.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "OWNER": PERMISSION_CATALOG[:],
    "ADMIN": [
        "users.read", "users.create", "users.update",
        "products.read", "products.create", "products.update", "products.delete",
        "orders.read", "orders.create", "orders.update", "orders.cancel",
        "inventory.read", "inventory.update",
        "finance.read", "finance.manage",
        "reports.read",
        "ai.execute", "ai.approve",
        "settings.manage",
        "customers.read", "customers.create", "customers.update", "customers.delete",
        "suppliers.read", "suppliers.create", "suppliers.update", "suppliers.delete",
        "channels.read", "channels.send",
    ],
    "MANAGER": [
        "users.read",
        "products.read", "products.create", "products.update",
        "orders.read", "orders.create", "orders.update", "orders.cancel",
        "inventory.read", "inventory.update",
        "finance.read",
        "reports.read",
        "ai.execute",
        "customers.read", "customers.create", "customers.update",
        "suppliers.read", "suppliers.create", "suppliers.update",
        "channels.read", "channels.send",
    ],
    "EMPLOYEE": [
        "products.read",
        "orders.read", "orders.create", "orders.update",
        "inventory.read",
        "customers.read", "customers.create",
        "suppliers.read",
        "channels.read", "channels.send",
    ],
    "ACCOUNTANT": [
        "finance.read", "finance.manage",
        "reports.read",
        "orders.read",
        "expenses.read", "expenses.create", "expenses.update",
        "suppliers.read",
    ],
    "VIEWER": [
        "products.read",
        "orders.read",
        "inventory.read",
        "finance.read",
        "reports.read",
        "customers.read",
        "suppliers.read",
    ],
    "AI_AGENT": [
        "products.read",
        "orders.read", "orders.create", "orders.update",
        "inventory.read", "inventory.update",
        "customers.read", "customers.create",
        "channels.read", "channels.send",
    ],
}


# --- Models -----------------------------------------------------------------
class Role(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    permissions = relationship(
        "Permission", secondary="role_permissions", back_populates="roles", lazy="selectin",
    )
    users = relationship("UserRole", back_populates="role")


class Permission(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "permissions"

    codename: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")


# Association: role <-> permission (many-to-many)
from sqlalchemy import Table, Column

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_role_permissions_role_id", "role_id"),
    Index("ix_role_permissions_permission_id", "permission_id"),
)


class User(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "users"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True,
    )

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Security
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Profile
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en-US")

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="users")
    roles_rel = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    @property
    def roles(self) -> list[str]:
        return [ur.role_name for ur in self.roles_rel]

    @property
    def permissions(self) -> set[str]:
        result: set[str] = set()
        for ur in self.roles_rel:
            if ur.role and ur.role.permissions:
                for p in ur.role.permissions:
                    result.add(p.codename)
        return result

    def has_permission(self, codename: str) -> bool:
        return self.is_superuser or codename in self.permissions


class UserRole(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), index=True, nullable=False)
    role_name: Mapped[str] = mapped_column(String(32), nullable=False)

    user = relationship("User", back_populates="roles_rel")
    role = relationship("Role")


class Session(Base, UUIDPkMixin, TimestampMixin):
    """Login session, paired with a refresh token (jti stored in token)."""

    __tablename__ = "sessions"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    organization_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True)

    refresh_token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user = relationship("User", back_populates="sessions")

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return True
        # Normalize: SQLite returns naive datetimes; assume UTC
        from app.utils.timezone import is_past
        return is_past(self.expires_at)

    def is_revoked(self) -> bool:
        return self.revoked_at is not None
