"""Data source schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectionConfig(BaseModel):
    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    # Extra driver-specific options
    ssl_mode: Optional[str] = None


class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    db_type: str = Field(..., pattern=r"^(postgresql|mysql|clickhouse|doris)$")
    connection_config: ConnectionConfig
    max_rows_per_query: int = Field(10000, ge=1, le=1000000)
    query_timeout: int = Field(30, ge=5, le=300)
    allowed_schemas: Optional[List[str]] = None
    denied_tables: Optional[List[str]] = None


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    connection_config: Optional[ConnectionConfig] = None
    max_rows_per_query: Optional[int] = None
    query_timeout: Optional[int] = None
    allowed_schemas: Optional[List[str]] = None
    denied_tables: Optional[List[str]] = None


class DataSourceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    db_type: str
    status: str
    last_tested_at: Optional[datetime]
    max_rows_per_query: int
    query_timeout: int
    allowed_schemas: List[str]
    denied_tables: List[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TableMetaResponse(BaseModel):
    id: UUID
    datasource_id: UUID
    schema_name: Optional[str]
    table_name: str
    table_comment: Optional[str]
    row_count_estimate: Optional[int]
    column_metas: List[Dict[str, Any]]
    last_synced_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TestConnectionResult(BaseModel):
    success: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None
