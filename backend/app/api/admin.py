"""Admin API — system management, audit logs, stats."""

import uuid
from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.dependencies import get_db, get_current_active_user, require_permissions
from app.models.audit import AuditLog
from app.models.user import User, Tenant
from app.schemas.audit import AuditLogQueryParams, AuditLogResponse, SystemStats

router = APIRouter()


@router.get("/tenants")
async def list_tenants(
    page: int = Query(1, ge=1),
    _=Depends(require_permissions(Permission.ADMIN_TENANTS.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tenant).offset((page - 1) * 20).limit(20))
    return result.scalars().all()


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    params: AuditLogQueryParams = Depends(),
    _=Depends(require_permissions(Permission.ADMIN_AUDIT.value)),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditLog)
    count_filters = []

    if params.tenant_id:
        query = query.where(AuditLog.tenant_id == params.tenant_id)
    if params.user_id:
        query = query.where(AuditLog.user_id == params.user_id)
    if params.action:
        query = query.where(AuditLog.action.ilike(f"%{params.action}%"))
    if params.resource_type:
        query = query.where(AuditLog.resource_type == params.resource_type)
    if params.start_date:
        query = query.where(AuditLog.created_at >= params.start_date)
    if params.end_date:
        query = query.where(AuditLog.created_at <= params.end_date)

    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar()

    result = await db.execute(
        query.order_by(desc(AuditLog.created_at))
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    logs = result.scalars().all()
    return [AuditLogResponse.model_validate(log) for log in logs]


@router.get("/stats", response_model=SystemStats)
async def system_stats(
    _=Depends(require_permissions(Permission.ADMIN_SETTINGS.value)),
    db: AsyncSession = Depends(get_db),
):
    async def count(model):
        return (await db.execute(select(func.count()).select_from(model))).scalar() or 0

    return SystemStats(
        total_tenants=await count(Tenant),
        total_users=await count(User),
    )


@router.get("/users")
async def admin_list_users(
    page: int = Query(1, ge=1),
    _=Depends(require_permissions(Permission.ADMIN_USERS.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).offset((page - 1) * 20).limit(20))
    return result.scalars().all()
