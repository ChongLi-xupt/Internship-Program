"""
Data source and table metadata models — Smart Query engine data layer.
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
    DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class DataSourceStatus(str, SAEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class DataSourceDBType(str, SAEnum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    CLICKHOUSE = "clickhouse"
    DORIS = "doris"


class DataSource(Base, TimestampMixin):
    __tablename__ = "datasources"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    db_type: Mapped[str] = mapped_column(String(16), nullable=False)
    connection_config_encrypted: Mapped[Optional[str]] = mapped_column(Text, name="connection_config")
    status: Mapped[str] = mapped_column(String(16), default="inactive")
    last_tested_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True))
    max_rows_per_query: Mapped[int] = mapped_column(Integer, default=10000)
    query_timeout: Mapped[int] = mapped_column(Integer, default=30)
    allowed_schemas_json: Mapped[Optional[List[str]]] = mapped_column(JSON, name="allowed_schemas")
    denied_tables_json: Mapped[Optional[List[str]]] = mapped_column(JSON, name="denied_tables")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))

    tenant: Mapped["Tenant"] = relationship(back_populates="datasources")
    table_metas: Mapped[List["TableMeta"]] = relationship(back_populates="datasource", cascade="all, delete-orphan")
    semantic_layers: Mapped[List["SemanticLayer"]] = relationship(back_populates="datasource", cascade="all, delete-orphan")
    sql_examples: Mapped[List["SQLExample"]] = relationship(back_populates="datasource", cascade="all, delete-orphan")
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="datasource", cascade="all, delete-orphan")

    @property
    def allowed_schemas(self) -> List[str]:
        return self.allowed_schemas_json or []

    @property
    def denied_tables(self) -> List[str]:
        return self.denied_tables_json or []


class TableMeta(Base, TimestampMixin):
    __tablename__ = "table_metas"

    id: Mapped[uuid.UUID] = uuid_pk()
    datasource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasources.id"), nullable=False)
    schema_name: Mapped[Optional[str]] = mapped_column(String(128))
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    table_comment: Mapped[Optional[str]] = mapped_column(Text)
    row_count_estimate: Mapped[Optional[int]] = mapped_column(BigInteger)
    column_metas_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, name="column_metas")
    last_synced_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True))

    datasource: Mapped["DataSource"] = relationship(back_populates="table_metas")

    __table_args__ = (
        Index("ix_tablemeta_ds_table", "datasource_id", "schema_name", "table_name"),
    )

    @property
    def column_metas(self) -> List[Dict[str, Any]]:
        return self.column_metas_json or []
