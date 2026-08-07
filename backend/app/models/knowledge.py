"""
Knowledge base, Document, Chunk models — RAG engine data layer.
"""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    String,
    Text,
    Integer,
    BigInteger,
    Boolean,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class KnowledgeBaseStatus(str, SAEnum):
    DRAFT = "draft"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class KnowledgeBase(Base, TimestampMixin):
    __tablename__ = "knowledge_bases"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(String(64), default="text-embedding-3-small")
    chunk_size: Mapped[int] = mapped_column(Integer, default=512)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50)
    rerank_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    rerank_model: Mapped[Optional[str]] = mapped_column(String(64))
    system_prompt: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    doc_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))

    tenant: Mapped["Tenant"] = relationship(back_populates="knowledge_bases")
    documents: Mapped[List["Document"]] = relationship(back_populates="knowledge_base", cascade="all, delete-orphan")
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="knowledge_base", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_kb_tenant_name", "tenant_id", "name"),
    )

    @property
    def qdrant_collection_name(self) -> str:
        from app.config import settings
        return f"{settings.qdrant_collection_prefix}{self.id}"


class DocumentParseStatus(str, SAEnum):
    PENDING = "pending"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentFileType(str, SAEnum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    MD = "md"
    XLSX = "xlsx"
    TXT = "txt"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_bases.id"), index=True, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512))
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(8), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024))
    source_url: Mapped[Optional[str]] = mapped_column(String(2048))
    parse_status: Mapped[str] = mapped_column(String(16), default="pending")
    parse_error: Mapped[Optional[str]] = mapped_column(Text)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, name="metadata")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    chunks: Mapped[List["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_doc_kb_status", "kb_id", "parse_status"),
    )

    @property
    def meta(self) -> Dict[str, Any]:
        return self.metadata_json or {}


class Chunk(Base):
    """Document chunk — stores text content + metadata. Vector stored in Qdrant separately."""
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True, nullable=False)
    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_bases.id"), index=True, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, name="metadata")

    document: Mapped["Document"] = relationship(back_populates="chunks")

    @property
    def meta(self) -> Dict[str, Any]:
        return self.metadata_json or {}
