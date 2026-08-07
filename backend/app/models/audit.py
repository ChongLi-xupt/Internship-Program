"""
Audit log model.
"""

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, String, Text, ForeignKey, Index, JSON, DateTime, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64))
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    detail_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, name="detail")
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6-safe
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_tenant_action", "tenant_id", "action"),
        Index("ix_audit_created", "created_at"),
    )

    @property
    def detail(self) -> Dict[str, Any]:
        return self.detail_json or {}
