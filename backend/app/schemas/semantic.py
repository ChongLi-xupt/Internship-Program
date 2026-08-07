"""Semantic layer schemas — metrics, dimensions, terminology, SQL examples."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# === Semantic Layer ===

class SemanticLayerCreate(BaseModel):
    datasource_id: UUID
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None


class SemanticLayerResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    datasource_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# === Metric ===

class MetricCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    aliases: Optional[List[str]] = None
    aggregation: str = Field(..., pattern=r"^(sum|avg|count|count_distinct|max|min)$")
    column_expr: str  # e.g., "SUM(o.total_amount)"
    source_table: Optional[str] = None
    unit: Optional[str] = None
    description: Optional[str] = None
    format_pattern: Optional[str] = None


class MetricResponse(MetricCreate):
    id: UUID
    layer_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# === Dimension ===

class DimensionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    aliases: Optional[List[str]] = None
    column_name: Optional[str] = None
    source_table: Optional[str] = None
    values: Optional[List[Dict[str, Any]]] = None  # [{label,value}]
    hierarchy: Optional[List[str]] = None
    time_granularity: str = "none"  # year|quarter|month|week|day|none


class DimensionResponse(DimensionCreate):
    id: UUID
    layer_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# === Terminology ===

class TerminologyCreate(BaseModel):
    term: str = Field(..., min_length=1, max_length=128)
    synonyms: Optional[List[str]] = None
    definition: Optional[str] = None
    domain: Optional[str] = None
    data_source_ref: Optional[str] = None


class TerminologyBatchImport(BaseModel):
    items: List[TerminologyCreate]


class TerminologyResponse(TerminologyCreate):
    id: UUID
    tenant_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# === SQL Example (Few-shot) ===

class SQLExampleCreate(BaseModel):
    datasource_id: UUID
    question: str  # Natural language question
    sql: str  # Standard SQL
    explanation: Optional[str] = None
    tags: Optional[List[str]] = None


class SQLExampleResponse(SQLExampleCreate):
    id: UUID
    tenant_id: UUID
    verified: bool
    usage_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
