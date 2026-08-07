"""
Role-Based Access Control (RBAC) permission definitions and helpers.
"""

from enum import Enum
from typing import ClassVar


class Permission(str, Enum):
    """All permission codes used in the system."""

    # Knowledge Base
    KB_READ = "kb:read"
    KB_WRITE = "kb:write"
    KB_DELETE = "kb:delete"
    KB_MANAGE = "kb:manage"

    # Document / Ingestion
    DOC_UPLOAD = "doc:upload"
    DOC_DELETE = "doc:delete"

    # Chat / Query
    CHAT_RAG = "chat:rag"
    CHAT_QUERY = "chat:query"

    # Data Source
    DS_READ = "ds:read"
    DS_WRITE = "ds:write"
    DS_QUERY = "ds:query"
    DS_MANAGE = "ds:manage"

    # Semantic Layer
    SEMANTIC_READ = "semantic:read"
    SEMANTIC_WRITE = "semantic:write"

    # Admin
    ADMIN_USERS = "admin:users"
    ADMIN_TENANTS = "admin:tenants"
    ADMIN_AUDIT = "admin:audit"
    ADMIN_SETTINGS = "admin:settings"


# Role → Permissions mapping
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "super_admin": [p.value for p in Permission],  # All permissions
    "tenant_admin": [
        Permission.KB_MANAGE,
        Permission.DOC_UPLOAD,
        Permission.DOC_DELETE,
        Permission.CHAT_RAG,
        Permission.CHAT_QUERY,
        Permission.DS_MANAGE,
        Permission.SEMANTIC_WRITE,
        Permission.ADMIN_USERS,
        Permission.ADMIN_AUDIT,
    ],
    "editor": [
        Permission.KB_WRITE,
        Permission.DOC_UPLOAD,
        Permission.CHAT_RAG,
        Permission.CHAT_QUERY,
        Permission.DS_WRITE,
        Permission.DS_QUERY,
        Permission.SEMANTIC_WRITE,
    ],
    "viewer": [
        Permission.KB_READ,
        Permission.CHAT_RAG,
        Permission.CHAT_QUERY,
        Permission.DS_READ,
        Permission.SEMANTIC_READ,
    ],
}


def get_role_permissions(role: str) -> list[str]:
    return ROLE_PERMISSIONS.get(role, [])


def has_permission(user_permissions: list[str], required: str) -> bool:
    """Check if user has a specific permission."""
    if f"admin:*" in user_permissions or "super_admin" in str(user_permissions):
        return True
    return required in user_permissions
