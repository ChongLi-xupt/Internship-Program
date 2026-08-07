"""Authentication API routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
)
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.user import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    PasswordChangeRequest,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """User login → returns access + refresh tokens."""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="账户已禁用")

    token_data = {"sub": str(user.id), "username": user.username, "role": user.role}

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/register", response_model=UserResponse)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user (creates default tenant)."""
    # Check existing
    existing = await db.execute(select(User).where((User.username == body.username) | (User.email == body.email)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名或邮箱已被注册")

    from app.models.user import Tenant

    # Create tenant
    tenant = Tenant(name=f"{body.full_name or body.username}的租户", slug=body.username.lower())
    db.add(tenant)
    await db.flush()

    # Create user
    user = User(
        tenant_id=tenant.id,
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role="tenant_admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token."""
    from app.core.security import decode_refresh_token

    payload = decode_refresh_token(refresh_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="无效的刷新令牌")

    new_token_data = {"sub": payload["sub"], "username": payload.get("username", ""), "role": payload.get("role", "")}

    return TokenResponse(
        access_token=create_access_token(new_token_data),
        refresh_token=create_refresh_token(new_token_data),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse.model_validate(current_user)


@router.put("/password")
async def change_password(
    body: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change current user's password."""
    if not verify_password(body.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码不正确")

    current_user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return {"message": "密码修改成功"}
