"""Knowledge base CRUD API."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.core.tenant import get_current_tenant_id
from app.dependencies import get_db, get_current_active_user, require_permissions
from app.models.knowledge import KnowledgeBase
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
)

router = APIRouter()


@router.post("", response_model=KnowledgeBaseResponse, status_code=201)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    current_user: User = Depends(require_permissions(Permission.KB_WRITE.value)),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = get_current_tenant_id() or str(current_user.tenant_id)

    kb = KnowledgeBase(
        tenant_id=uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id,
        name=body.name,
        description=body.description,
        embedding_model=body.embedding_model,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        rerank_enabled=body.rerank_enabled,
        rerank_model=body.rerank_model,
        system_prompt=body.system_prompt,
        created_by=current_user.id,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)

    # Create vector collection
    try:
        from app.vector.base import get_vector_store
        store = get_vector_store()
        await store.create_collection(kb.qdrant_collection_name, 1536)
    except Exception:
        pass  # Collection may already exist or will be created on first ingest

    return KnowledgeBaseResponse.model_validate(kb)


@router.get("", response_model=List[KnowledgeBaseResponse])
async def list_knowledge_bases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = get_current_tenant_id() or str(current_user.tenant_id)
    query = select(KnowledgeBase).where(KnowledgeBase.tenant_id == uuid.UUID(tenant_id))

    if search:
        query = query.where(KnowledgeBase.name.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    result = await db.execute(query.order_by(KnowledgeBase.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    kbs = result.scalars().all()

    return [KnowledgeBaseResponse.model_validate(kb) for kb in kbs]


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return KnowledgeBaseResponse.model_validate(kb)


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: uuid.UUID,
    body: KnowledgeBaseUpdate,
    current_user: User = Depends(require_permissions(Permission.KB_MANAGE.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(kb, field, value)

    await db.commit()
    await db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    _=Depends(require_permissions(Permission.KB_DELETE.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # Delete vector collection
    try:
        from app.vector.base import get_vector_store
        store = get_vector_store()
        await store.delete_collection(kb.qdrant_collection_name)
    except Exception:
        pass

    await db.delete(kb)
    await db.commit()
    return {"message": "知识库已删除"}
