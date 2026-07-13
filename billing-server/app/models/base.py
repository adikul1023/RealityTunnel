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


class SubscriptionLifecycleStatus(str, enum.Enum):
    """
    PostgreSQL ENUM for specific subscription lifecycle states (Phase 2.1).
    """
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    GRACE = "GRACE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class RevocationReason(str, enum.Enum):
    """
    Reason a refresh token was revoked.
    """
    ROTATED = "ROTATED"
    DEVICE_REMOVED = "DEVICE_REMOVED"
    USER_LOGOUT = "USER_LOGOUT"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    PASSWORD_RESET = "PASSWORD_RESET"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    SUBSCRIPTION_REVOKED = "SUBSCRIPTION_REVOKED"


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
