"""Knowledge base & document schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# === Knowledge Base ===

class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = Field(512, ge=100, le=4096)
    chunk_overlap: int = Field(50, ge=0, le=500)
    rerank_enabled: bool = False
    rerank_model: Optional[str] = None
    system_prompt: Optional[str] = None


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    embedding_model: Optional[str] = None
    chunk_size: Optional[int] = Field(None, ge=100, le=4096)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=500)
    rerank_enabled: Optional[bool] = None
    rerank_model: Optional[str] = None
    system_prompt: Optional[str] = None


class KnowledgeBaseResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    rerank_enabled: bool
    rerank_model: Optional[str]
    status: str
    doc_count: int
    chunk_count: int
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# === Document ===

class DocumentUploadResponse(BaseModel):
    document_id: UUID
    file_name: str
    status: str = "parsing"
    message: str = "文档已接收，正在后台处理"


class DocumentResponse(BaseModel):
    id: UUID
    kb_id: UUID
    title: Optional[str]
    file_name: str
    file_type: str
    file_size: Optional[int]
    parse_status: str
    page_count: Optional[int]
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkResponse(BaseModel):
    id: int
    document_id: UUID
    content: str
    chunk_index: int
    token_count: Optional[int]
    metadata: dict[str, Any]

    model_config = {"from_attributes": True}


class DocumentListParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    status: Optional[str] = None
    search: Optional[str] = None
