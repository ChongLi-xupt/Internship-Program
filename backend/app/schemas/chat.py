"""
Chat / unified messaging schemas.
This is the core API contract between frontend and backend.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# === Chat Request ===

class ChatMessageRequest(BaseModel):
    """Unified chat request for both RAG and Smart Query engines."""
    conversation_id: Optional[UUID] = None  # Omit to create new conversation
    engine: str = Field(..., pattern="^(rag|query)$")
    message: str = Field(..., min_length=1, max_length=4000)
    kb_id: Optional[UUID] = None  # Required when engine=rag
    datasource_id: Optional[UUID] = None  # Optional when engine=query (use default)
    stream: bool = True  # SSE streaming or full response


# === SSE Event Types ===

class ThinkingEvent(BaseModel):
    content: str


class RetrievalSource(BaseModel):
    doc_title: str
    chunk_content: str
    score: float
    document_id: UUID
    chunk_index: int


class RetrievalResultEvent(BaseModel):
    sources: List[RetrievalSource]


class QueryIntentEvent(BaseModel):
    intent: Dict[str, Any]  # {type, metrics, dimensions, filters, time_range,...}


class SQLGeneratedEvent(BaseModel):
    sql: str


class ResultDataEvent(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    executed_sql: Optional[str] = None
    execution_time_ms: Optional[float] = None


class ChartRecommendationEvent(BaseModel):
    type: str  # bar | line | pie | scatter | table | number
    config: Dict[str, Any]


class MessageDeltaEvent(BaseModel):
    content: str


class MessageMetadata(BaseModel):
    sources: Optional[List[RetrievalSource]] = None
    sql: Optional[str] = None
    chart_config: Optional[Dict[str, Any]] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None
    confidence: Optional[float] = None


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class MessageDoneEvent(BaseModel):
    message_id: UUID
    conversation_id: UUID
    metadata: MessageMetadata
    usage: UsageInfo


# === Non-streaming Response ===

class ChatResponse(BaseModel):
    message_id: UUID
    conversation_id: UUID
    content: str
    message_type: str = "text"
    metadata: MessageMetadata
    usage: UsageInfo


# === Conversation ===

class ConversationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    engine: str
    kb_id: Optional[UUID]
    datasource_id: Optional[UUID]
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationListParams(BaseModel):
    engine: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class MessageListResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    message_type: str
    metadata: Dict[str, Any]
    token_count: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
