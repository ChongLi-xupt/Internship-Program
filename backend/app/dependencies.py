"""
Dependency injection utilities:
- Async DB session
- Current user from JWT
- Current tenant context
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decode_access_token
from app.core.tenant import set_tenant_context, get_current_tenant_id
from app.database import get_async_session
from app.models.user import User


security_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session."""
    async with get_async_session() as session:
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> User:
    """Extract and validate JWT → return current User or raise 401."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")

    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Set tenant context for this request
    set_tenant_context(str(user.tenant_id))
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensure user account is active."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_optional_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> User | None:
    """Try to get current user but don't raise if missing (for public endpoints)."""
    if credentials is None:
        return None
    try:
        return await get_current_user(db, credentials)
    except HTTPException:
        return None


def require_permissions(*required: str):
    """Factory that returns a dependency checking RBAC permissions."""

    async def _check(user: User = Depends(get_current_active_user)) -> User:
        user_perms = set(getattr(user, "permissions", []) or [])
        if not any(r in user_perms for r in required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _check
