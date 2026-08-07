"""
Semantic layer, Metric, Dimension, Terminology, SQL Example models.
These form the "semantic intermediary" between natural language and SQL.
"""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class SemanticLayer(Base, TimestampMixin):
    """Logical grouping of metrics & dimensions (e.g., 'Sales Analytics Domain')."""
    __tablename__ = "semantic_layers"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    datasource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasources.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    datasource: Mapped["DataSource"] = relationship(back_populates="semantic_layers")
    metrics: Mapped[List["Metric"]] = relationship(back_populates="layer", cascade="all, delete-orphan")
    dimensions: Mapped[List["Dimension"]] = relationship(back_populates="layer", cascade="all, delete-orphan")


class AggregationType(str, SAEnum):
    SUM = "sum"
    AVG = "avg"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    MAX = "max"
    MIN = "min"


class TimeGranularity(str, SAEnum):
    YEAR = "year"
    QUARTER = "quarter"
    MONTH = "month"
    WEEK = "week"
    DAY = "day"
    NONE = "none"


class Metric(Base, TimestampMixin):
    """Business metric definition (e.g., 'Sales Amount' → SUM(o.total_amount))."""
    __tablename__ = "metrics"

    id: Mapped[uuid.UUID] = uuid_pk()
    layer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_layers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)  # Display name
    aliases_json: Mapped[Optional[List[str]]] = mapped_column(JSON, name="aliases")
    aggregation: Mapped[str] = mapped_column(String(20), nullable=False)  # sum|avg|count|...
    column_expr: Mapped[str] = mapped_column(Text, nullable=False)  # SQL expression
    source_table: Mapped[Optional[str]] = mapped_column(String(128))
    unit: Mapped[Optional[str]] = mapped_column(String(32))  # 元, %, 人
    description: Mapped[Optional[str]] = mapped_column(Text)
    format_pattern: Mapped[Optional[str]] = mapped_column(String(64))

    layer: Mapped["SemanticLayer"] = relationship(back_populates="metrics")

    @property
    def aliases(self) -> List[str]:
        return self.aliases_json or []


class Dimension(Base, TimestampMixin):
    """Business dimension definition (e.g., 'Region' → o.region)."""
    __tablename__ = "dimensions"

    id: Mapped[uuid.UUID] = uuid_pk()
    layer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_layers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    aliases_json: Mapped[Optional[List[str]]] = mapped_column(JSON, name="aliases")
    column_name: Mapped[Optional[str]] = mapped_column(String(128))
    source_table: Mapped[Optional[str]] = mapped_column(String(128))
    values_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, name="values")  # [{label,value}]
    hierarchy_json: Mapped[Optional[List[str]]] = mapped_column(JSON, name="hierarchy")  # [大区,省,市]
    time_granularity: Mapped[str] = mapped_column(String(8), default="none")

    layer: Mapped["SemanticLayer"] = relationship(back_populates="dimensions")

    @property
    def aliases(self) -> List[str]:
        return self.aliases_json or []

    @property
    def values(self) -> List[Dict[str, Any]]:
        return self.values_json or []

    @property
    def hierarchy(self) -> List[str]:
        return self.hierarchy_json or []


class Terminology(Base, TimestampMixin):
    """Business terminology / synonym dictionary."""
    __tablename__ = "terminologies"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    term: Mapped[str] = mapped_column(String(128), nullable=False)  # Standard term
    synonyms_json: Mapped[Optional[List[str]]] = mapped_column(JSON, name="synonyms")
    definition: Mapped[Optional[str]] = mapped_column(Text)
    domain: Mapped[Optional[str]] = mapped_column(String(128))
    data_source_ref: Mapped[Optional[str]] = mapped_column(String(256))

    __table_args__ = (
        Index("ix_term_tenant_term", "tenant_id", "term"),
    )

    @property
    def synonyms(self) -> List[str]:
        return self.synonyms_json or []


class SQLExample(Base, TimestampMixin):
    """Few-shot SQL examples for NL2SQL (maintained by DBA + prompt engineers)."""
    __tablename__ = "sql_examples"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    datasource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasources.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)  # Natural language question
    sql: Mapped[str] = mapped_column(Text, nullable=False)  # Corresponding standard SQL
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    tags_json: Mapped[Optional[List[str]]] = mapped_column(JSON, name="tags")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)  # DBA reviewed?
    usage_count: Mapped[int] = mapped_column(Integer, default=0)

    datasource: Mapped["DataSource"] = relationship(back_populates="sql_examples")

    @property
    def tags(self) -> List[str]:
        return self.tags_json or []
