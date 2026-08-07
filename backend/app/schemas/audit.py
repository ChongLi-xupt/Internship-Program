"""Audit log schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    id: int
    tenant_id: Optional[UUID]
    user_id: Optional[UUID]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[UUID]
    detail: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogQueryParams(BaseModel):
    tenant_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)


class SystemStats(BaseModel):
    total_tenants: int = 0
    total_users: int = 0
    total_knowledge_bases: int = 0
    total_documents: int = 0
    total_chunks: int = 0
    total_datasources: int = 0
    total_conversations: int = 0
    total_messages: int = 0
    active_users_24h: int = 0
    chat_requests_today: int = 0
