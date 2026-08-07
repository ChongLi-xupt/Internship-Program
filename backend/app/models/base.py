"""
SQLAlchemy Base class with common columns.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base for all ORM models."""

    pass


class TimestampMixin:
    """Reusable created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def uuid_pk() -> Mapped[uuid.UUID]:
    """
    Build a fresh UUID primary-key column.

    Must be a factory, not a shared class attribute: a ``MappedColumn`` is
    bound to exactly one mapper, so reusing a single instance across models
    silently corrupts the metadata (and passing one back into
    ``mapped_column()`` raises ``ArgumentError`` outright).
    """
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class UUIDPrimaryKey:
    """
    Deprecated. Kept only so old imports do not explode.

    Use :func:`uuid_pk` instead — ``mapped_column(UUIDPrimaryKey.id)`` is not
    a valid SQLAlchemy 2.x construct.
    """

    __slots__ = ()


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
