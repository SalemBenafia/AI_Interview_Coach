"""
app/common/models.py
=====================
Shared SQLAlchemy mixins for all domain models.
Every table inherits TimestampMixin + UUIDMixin, and optionally SoftDeleteMixin.

Unlike the original CallBot platform, the AI Interview Coach is NOT
multi-tenant (no TenantMixin) — per roles.txt there are exactly three
actors: Candidate (User), Admin, and the AI Agent System. Admins manage the
whole platform directly; there is no per-organization data isolation layer.
If org-level isolation is needed later (e.g. university/bootcamp cohorts),
re-introduce a TenantMixin the same way the original platform did.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    """UUID primary key."""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


class TimestampMixin:
    """Automatic created_at / updated_at timestamps."""
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


class SoftDeleteMixin:
    """Soft delete — never hard-delete user/candidate data."""
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class BaseModel(UUIDMixin, TimestampMixin):
    """Base model with UUID PK and timestamps. Used by most tables."""
    pass


class SoftDeleteModel(UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Base model with UUID PK, timestamps, and soft delete support."""
    pass
