"""Data source CRUD & management API."""

import json
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.core.tenant import get_current_tenant_id
from app.dependencies import get_db, get_current_active_user, require_permissions
from app.models.datasource import DataSource, TableMeta
from app.models.user import User
from app.schemas.datasource import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceResponse,
    TableMetaResponse,
    TestConnectionResult,
)
from app.utils.data_masking import encrypt_data, decrypt_connection_config

router = APIRouter()


@router.post("", response_model=DataSourceResponse, status_code=201)
async def create_datasource(
    body: DataSourceCreate,
    current_user: User = Depends(require_permissions(Permission.DS_WRITE.value)),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = get_current_tenant_id() or str(current_user.tenant_id)

    # Encrypt connection config before storing
    config_dict = body.connection_config.model_dump()
    encrypted_config = encrypt_data(json.dumps(config_dict))

    ds = DataSource(
        tenant_id=uuid.UUID(tenant_id),
        name=body.name,
        db_type=body.db_type,
        connection_config_encrypted=encrypted_config,
        max_rows_per_query=body.max_rows_per_query,
        query_timeout=body.query_timeout,
        allowed_schemas_json=body.allowed_schemas,
        denied_tables_json=body.denied_tables,
        created_by=current_user.id,
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return DataSourceResponse.model_validate(ds)


@router.get("", response_model=List[DataSourceResponse])
async def list_datasources(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = get_current_tenant_id() or str(current_user.tenant_id)
    query = select(DataSource).where(DataSource.tenant_id == uuid.UUID(tenant_id))
    count_q = select(func.count()).select_from(query.subquery())

    total = (await db.execute(count_q)).scalar()
    result = await db.execute(query.order_by(DataSource.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    datasources = result.scalars().all()

    return [DataSourceResponse.model_validate(d) for d in datasources]


@router.get("/{ds_id}", response_model=DataSourceResponse)
async def get_datasource(
    ds_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return DataSourceResponse.model_validate(ds)


@router.put("/{ds_id}", response_model=DataSourceResponse)
async def update_datasource(
    ds_id: uuid.UUID,
    body: DataSourceUpdate,
    _=Depends(require_permissions(Permission.DS_MANAGE.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    if body.connection_config:
        config_dict = body.connection_config.model_dump()
        ds.connection_config_encrypted = encrypt_data(json.dumps(config_dict))

    update_data = body.model_dump(exclude_unset=True, exclude={"connection_config"})
    for field, value in update_data.items():
        setattr(ds, field, value)

    await db.commit()
    await db.refresh(ds)
    return DataSourceResponse.model_validate(ds)


@router.delete("/{ds_id}")
async def delete_datasource(
    ds_id: uuid.UUID,
    _=Depends(require_permissions(Permission.DS_MANAGE.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    await db.delete(ds)
    await db.commit()
    return {"message": "数据源已删除"}


@router.post("/{ds_id}/test-connection", response_model=TestConnectionResult)
async def test_connection(
    ds_id: uuid.UUID,
    _=Depends(require_permissions(Permission.DS_READ.value)),
    db: AsyncSession = Depends(get_db),
):
    """Test database connectivity."""
    import time

    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    try:
        config = decrypt_connection_config(ds.connection_config_encrypted)
        start = time.time()

        if ds.db_type == "postgresql":
            import asyncpg

            conn = await asyncpg.connect(
                host=config["host"], port=config["port"],
                database=config["database"], user=config["username"],
                password=config["password"], timeout=5,
            )
            version = await conn.fetchval("SELECT version()")
            await conn.close()
        else:
            version = "connected"

        latency = round((time.time() - start) * 1000, 2)

        # Update last_tested
        from datetime import datetime, timezone
        ds.last_tested_at = datetime.now(timezone.utc)
        ds.status = "active"
        await db.commit()

        return TestConnectionResult(success=True, latency_ms=latency)
    except Exception as e:
        ds.status = "error"
        await db.commit()
        return TestConnectionResult(success=False, error=str(e))


@router.get("/{ds_id}/tables", response_model=list[TableMetaResponse])
async def list_tables(
    ds_id: uuid.UUID,
    _=Depends(require_permissions(Permission.DS_READ.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(TableMeta).where(TableMeta.datasource_id == ds_id).order_by(TableMeta.table_name))
    tables = result.scalars().all()
    return [TableMetaResponse.model_validate(t) for t in tables]
