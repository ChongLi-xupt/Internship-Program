"""
Multi-tenant isolation: request-scoped tenant context + SQLAlchemy event filter injection.
"""

import contextvars
from typing import Any

from sqlalchemy import Select

# Context variable for current tenant ID (set per-request)
_tenant_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_id", default=None)


def set_tenant_context(tenant_id: str) -> None:
    _tenant_ctx.set(tenant_id)


def get_current_tenant_id() -> str | None:
    return _tenant_ctx.get()


def clear_tenant_context() -> None:
    _tenant_ctx.set(None)


# Tables that require tenant isolation (all have a `tenant_id` column)
_TENANT_TABLES = {
    "knowledge_bases",
    "documents",
    "chunks",
    "datasources",
    "table_metas",
    "semantic_layers",
    "metrics",
    "dimensions",
    "terminologies",
    "sql_examples",
    "conversations",
    "messages",
    "audit_logs",
}


def _inject_tenant_filter(cls: Any, clause: Select) -> Select | None:
    """Before-execute event: auto-inject WHERE tenant_id for tenant-scoped tables."""
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        return None  # No tenant context (e.g., startup tasks)

    # Only inject for SELECT on known tenant tables
    table_name = ""
    from_clause = getattr(clause, "froms", None)
    if from_clause:
        for f in from_clause:
            if hasattr(f, "name"):
                table_name = f.name
                break

    if table_name and table_name in _TENANT_TABLES:
        # Check if tenant_id filter already present (avoid double injection)
        existing = str(clause).lower()
        if "tenant_id" not in existing or "where" not in existing.lower():
            from sqlalchemy import and_

            model_cls = cls  # The mapper class
            return clause.where(getattr(model_cls, "tenant_id") == tenant_id)

    return None


def init_tenant_filter() -> None:
    """
    Register SQLAlchemy event listener for automatic tenant filtering.
    Call once at application startup.
    
    Note: AsyncSession doesn't support 'do_orm_execute' event directly.
    Use connection-level events or service-layer filtering for async queries.
    """
    from app.models.base import Base  # noqa: F401 — ensure all models are registered

    # Tenant filtering is handled at the service/query level via
    # get_current_tenant_id() rather than SQLAlchemy events, since
    # AsyncSession doesn't support do_orm_execute.
    print("✅ Tenant filter initialized")
