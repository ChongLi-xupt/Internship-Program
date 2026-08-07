"""Semantic layer, Terminology, SQL Examples CRUD API."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.dependencies import get_db, get_current_active_user, require_permissions
from app.models.semantic import (
    SemanticLayer, Metric, Dimension, Terminology, SQLExample,
)
from app.schemas.semantic import (
    SemanticLayerCreate, SemanticLayerResponse,
    MetricCreate, MetricResponse,
    DimensionCreate, DimensionResponse,
    TerminologyCreate, TerminologyBatchImport, TerminologyResponse,
    SQLExampleCreate, SQLExampleResponse,
)

router = APIRouter()


# ── Semantic Layer ──

@router.post("/layers", response_model=SemanticLayerResponse, status_code=201)
async def create_layer(
    body: SemanticLayerCreate,
    _=Depends(require_permissions(Permission.SEMANTIC_WRITE.value)),
    db: AsyncSession = Depends(get_db),
):
    layer = SemanticLayer(
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),  # Will be set by middleware
        datasource_id=body.datasource_id,
        name=body.name,
        description=body.description,
    )
    db.add(layer)
    await db.commit()
    await db.refresh(layer)
    return SemanticLayerResponse.model_validate(layer)


@router.get("/layers/{layer_id}/metrics", response_model=list[MetricResponse])
async def list_metrics(layer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Metric).where(Metric.layer_id == layer_id))
    return [MetricResponse.model_validate(m) for m in result.scalars().all()]


@router.post("/layers/{layer_id}/metrics", response_model=MetricResponse, status_code=201)
async def create_metric(
    layer_id: uuid.UUID,
    body: MetricCreate,
    _=Depends(require_permissions(Permission.SEMANTIC_WRITE.value)),
    db: AsyncSession = Depends(get_db),
):
    metric = Metric(layer_id=layer_id, **body.model_dump())
    db.add(metric)
    await db.commit()
    await db.refresh(metric)
    return MetricResponse.model_validate(metric)


@router.get("/layers/{layer_id}/dimensions", response_model=list[DimensionResponse])
async def list_dimensions(layer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dimension).where(Dimension.layer_id == layer_id))
    return [DimensionResponse.model_validate(d) for d in result.scalars().all()]


@router.post("/layers/{layer_id}/dimensions", response_model=DimensionResponse, status_code=201)
async def create_dimension(
    layer_id: uuid.UUID,
    body: DimensionCreate,
    _=Depends(require_permissions(Permission.SEMANTIC_WRITE.value)),
    db: AsyncSession = Depends(get_db),
):
    dim = Dimension(layer_id=layer_id, **body.model_dump())
    db.add(dim)
    await db.commit()
    await db.refresh(dim)
    return DimensionResponse.model_validate(dim)


# ── Terminology ──

@router.get("/terminology", response_model=list[TerminologyResponse])
async def list_terminology(
    q: str | None = Query(None, alias="q"),
    domain: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Terminology)
    if q:
        query = query.where(Terminology.term.ilike(f"%{q}%"))
    if domain:
        query = query.where(Terminology.domain == domain)

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    terms = result.scalars().all()
    return [TerminologyResponse.model_validate(t) for t in terms]


@router.post("/terminology", response_model=TerminologyResponse, status_code=201)
async def create_terminology(
    body: TerminologyCreate,
    _=Depends(require_permissions(Permission.SEMANTIC_WRITE.value)),
    db: AsyncSession = Depends(get_db),
):
    term = Terminology(**body.model_dump())
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return TerminologyResponse.model_validate(term)


@router.post("/terminology/batch-import", status_code=201)
async def batch_import_terminology(
    body: TerminologyBatchImport,
    _=Depends(require_permissions(Permission.SEMANTIC_WRITE.value)),
    db: AsyncSession = Depends(get_db),
):
    imported = 0
    for item in body.items:
        term = Terminology(**item.model_dump())
        db.add(term)
        imported += 1
    await db.commit()
    return {"message": f"成功导入 {imported} 条术语"}


# ── SQL Examples (Few-shot) ──

@router.get("/sql-examples", response_model=list[SQLExampleResponse])
async def list_sql_examples(
    datasource_id: uuid.UUID | None = None,
    verified_only: bool = False,
    tags: str | None = None,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(SQLExample)
    if datasource_id:
        query = query.where(SQLExample.datasource_id == datasource_id)
    if verified_only:
        query = query.where(SQLExample.verified == True)  # type: ignore
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        # JSON contains filter simplified
        query = query.limit(50)

    result = await db.execute(query.order_by(SQLExample.usage_count.desc()))
    return [SQLExampleResponse.model_validate(e) for e in result.scalars().all()]


@router.post("/sql-examples", response_model=SQLExampleResponse, status_code=201)
async def create_sql_example(
    body: SQLExampleCreate,
    _=Depends(require_permissions(Permission.SEMANTIC_WRITE.value)),
    db: AsyncSession = Depends(get_db),
):
    example = SQLExample(**body.model_dump())
    db.add(example)
    await db.commit()
    await db.refresh(example)
    return SQLExampleResponse.model_validate(example)


@router.post("/sql-examples/{example_id}/verify")
async def verify_sql_example(
    example_id: uuid.UUID,
    _=Depends(require_permissions(Permission.SEMANTIC_WRITE.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SQLExample).where(SQLExample.id == example_id))
    ex = result.scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail="示例不存在")
    ex.verified = True
    await db.commit()
    return {"message": "示例已审核通过"}
