"""
Bootstrap the database: create tables, then seed the default tenant + admin.

Idempotent by design — safe to run on every container start. This stands in
for Alembic until real migrations exist; once they do, replace the
``create_all`` call with ``alembic upgrade head`` and keep the seeding half.

Usage:
    python -m scripts.init_db
"""

import asyncio
import os
import sys
from pathlib import Path

# Allow `python scripts/init_db.py` as well as `python -m scripts.init_db`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

import app.models  # noqa: F401,E402  — registers every mapper on Base.metadata
from app.core.security import hash_password  # noqa: E402
from app.database import async_session_factory, engine  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.user import Tenant, User  # noqa: E402

WAIT_SECONDS = int(os.getenv("DB_WAIT_SECONDS", "60"))


async def wait_for_db() -> None:
    """Poll until Postgres accepts connections (compose healthcheck can lie)."""
    from sqlalchemy import text

    for attempt in range(WAIT_SECONDS):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except (OperationalError, OSError) as exc:
            if attempt == 0:
                print(f"⏳ waiting for database … ({exc.__class__.__name__})")
            await asyncio.sleep(1)
    raise RuntimeError(f"database unreachable after {WAIT_SECONDS}s")


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ schema ready — {len(Base.metadata.tables)} tables")


async def seed_admin() -> None:
    """Create the bootstrap tenant + super admin if they are missing."""
    tenant_slug = os.getenv("INIT_TENANT_SLUG", "default")
    tenant_name = os.getenv("INIT_TENANT_NAME", "Default Tenant")
    username = os.getenv("INIT_ADMIN_USERNAME", "admin")
    password = os.getenv("INIT_ADMIN_PASSWORD", "admin123456")
    email = os.getenv("INIT_ADMIN_EMAIL", "admin@example.com")

    async with async_session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        ).scalar_one_or_none()

        if tenant is None:
            tenant = Tenant(
                name=tenant_name,
                slug=tenant_slug,
                plan="enterprise",
                max_kbs=100,
                max_docs_per_kb=100000,
                max_datasources=50,
            )
            session.add(tenant)
            await session.flush()
            print(f"✅ tenant created: {tenant_name} ({tenant_slug})")
        else:
            print(f"↩️  tenant exists: {tenant.name} ({tenant_slug})")

        user = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()

        if user is None:
            session.add(
                User(
                    tenant_id=tenant.id,
                    username=username,
                    email=email,
                    hashed_password=hash_password(password),
                    full_name="Super Admin",
                    role="super_admin",
                    is_active=True,
                )
            )
            print(f"✅ admin created: {username} / {password}")
        else:
            print(f"↩️  admin exists: {username}")

        await session.commit()


async def main() -> None:
    await wait_for_db()
    await create_tables()
    await seed_admin()
    await engine.dispose()
    print("🎉 database bootstrap complete")


if __name__ == "__main__":
    asyncio.run(main())
