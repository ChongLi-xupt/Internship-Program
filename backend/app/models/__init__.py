"""Import all models so SQLAlchemy picks them up for Base.metadata."""

from app.models.user import Tenant, User  # noqa: F401
from app.models.knowledge import KnowledgeBase, Document, Chunk  # noqa: F401
from app.models.datasource import DataSource, TableMeta  # noqa: F401
from app.models.semantic import (  # noqa: F401
    SemanticLayer,
    Metric,
    Dimension,
    Terminology,
    SQLExample,
)
from app.models.conversation import Conversation, Message  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401

__all__ = [
    "Tenant",
    "User",
    "KnowledgeBase",
    "Document",
    "Chunk",
    "DataSource",
    "TableMeta",
    "SemanticLayer",
    "Metric",
    "Dimension",
    "Terminology",
    "SQLExample",
    "Conversation",
    "Message",
    "AuditLog",
]
