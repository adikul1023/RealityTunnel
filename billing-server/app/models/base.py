"""
base.py — Shared base mixins and common enumerations for billing models.
"""
from __future__ import annotations

import enum
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class SubscriptionStatus(str, enum.Enum):
    """
    PostgreSQL ENUM for subscription status.
    Enforces valid state boundaries at the database layer.
    """
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    PENDING = "PENDING"


class TimestampMixin:
    """
    Mixin that provides automatic created_at and updated_at timestamps
    with server-side defaults and update triggers.
    """
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
