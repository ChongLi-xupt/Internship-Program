"""User management API routes."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Permission
from app.dependencies import get_db, get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.user import UserUpdate, UserResponse

router = APIRouter()


@router.get("", response_model=List[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = None,
    _=Depends(require_permissions(Permission.ADMIN_USERS.value)),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    count_query = select(func.count(User.id))

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    total = (await db.execute(count_query)).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    users = result.scalars().all()

    return [UserResponse.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    _=Depends(require_permissions(Permission.ADMIN_USERS.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserResponse.model_validate(user)


@router.put("/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    body: UserUpdate,
    _=Depends(require_permissions(Permission.ADMIN_USERS.value)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    return {"message": "用户信息更新成功"}
