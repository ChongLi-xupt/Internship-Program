"""
User, Tenant, Role models — authentication & multi-tenancy foundation.
"""

import uuid
from typing import List, Optional

from sqlalchemy import String, Text, Boolean, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="free")
    max_kbs: Mapped[int] = mapped_column(default=5)
    max_docs_per_kb: Mapped[int] = mapped_column(default=1000)
    max_datasources: Mapped[int] = mapped_column(default=3)
    # JSON field for tenant-level config (stored as TEXT in SQLite compat mode)
    settings_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="settings")

    users: Mapped[List["User"]] = relationship(back_populates="tenant")
    knowledge_bases: Mapped[List["KnowledgeBase"]] = relationship(back_populates="tenant")
    datasources: Mapped[List["DataSource"]] = relationship(back_populates="tenant")

    def __repr__(self) -> str:
        return f"<Tenant {self.name}>"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), default="viewer")  # super_admin | tenant_admin | editor | viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="users")

    @property
    def permissions(self) -> List[str]:
        from app.core.rbac import get_role_permissions
        return get_role_permissions(self.role)

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"
