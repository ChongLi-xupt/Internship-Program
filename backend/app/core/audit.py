"""
Audit logging service. Records all significant actions for compliance.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import get_current_tenant_id


async def log_audit(
    db: AsyncSession,
    *,
    user_id: str,
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    detail: dict[str, Any] | None = None,
    ip_address: str = "",
    user_agent: str = "",
) -> None:
    """Write an audit log entry asynchronously."""
    from app.models.audit import AuditLog

    entry = AuditLog(
        tenant_id=get_current_tenant_id() or "",
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail or {},
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()


class AuditContextManager:
    """Context manager that captures timing and logs audit entry on exit."""

    def __init__(
        self,
        db: AsyncSession,
        user_id: str,
        action: str,
        resource_type: str = "",
        resource_id: str = "",
        ip_address: str = "",
        user_agent: str = "",
    ):
        self.db = db
        self.user_id = user_id
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.start_time: float = 0
        self.extra_detail: dict[str, Any] = {}

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        detail = {**self.extra_detail, "duration_ms": round((time.time() - self.start_time) * 1000, 2)}
        if exc_val:
            detail["error"] = str(exc_val)
        # Fire-and-forget audit write
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    log_audit(
                        self.db,
                        user_id=self.user_id,
                        action=self.action,
                        resource_type=self.resource_type,
                        resource_id=self.resource_id,
                        detail=detail,
                        ip_address=self.ip_address,
                        user_agent=self.user_agent,
                    )
                )
        except RuntimeError:
            pass
        return False  # Don't suppress exceptions
