"""
Conversation and Message models — chat history for both RAG and Query engines.
"""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    DateTime,
    String,
    Text,
    Integer,
    ForeignKey,
    Index,
    JSON,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class ConversationEngine(str, enum.Enum):
    RAG = "rag"
    QUERY = "query"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(str, enum.Enum):
    TEXT = "text"
    CHART = "chart"
    TABLE = "table"
    MIXED = "mixed"


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    engine: Mapped[str] = mapped_column(String(8), nullable=False)  # rag | query
    kb_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("knowledge_bases.id"))
    datasource_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("datasources.id"))
    title: Mapped[Optional[str]] = mapped_column(String(256))

    knowledge_base: Mapped[Optional["KnowledgeBase"]] = relationship(back_populates="conversations")
    datasource: Mapped[Optional["DataSource"]] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )

    __table_args__ = (
        Index("ix_conv_user_engine", "user_id", "engine"),
    )


class Message(Base):
    """Single message in a conversation."""
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(16), default="text")  # text | chart | table | mixed
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    @property
    def meta(self) -> Dict[str, Any]:
        return self.metadata_json or {}

    @meta.setter
    def meta(self, value: Dict[str, Any]):
        self.metadata_json = value
