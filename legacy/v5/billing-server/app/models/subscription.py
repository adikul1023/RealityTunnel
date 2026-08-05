"""
subscription.py — Subscription entity representing account billing subscription contracts.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base
from app.models.base import SubscriptionLifecycleStatus, TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account


class Subscription(Base, TimestampMixin):
    """
    Subscriptions table (Phase 2.1).
    Stores independent subscription lifecycle state, plan association, timestamps, and renewal status.
    Never stores payment gateway tokens or credit card data.
    """
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        default="free",
        server_default="free",
    )
    status: Mapped[SubscriptionLifecycleStatus] = mapped_column(
        SQLEnum(
            SubscriptionLifecycleStatus,
            name="subscription_lifecycle_status",
            create_constraint=True,
            native_enum=True,
        ),
        default=SubscriptionLifecycleStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    grace_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    auto_renew: Mapped[bool] = mapped_column(
        Boolean(),
        default=True,
        server_default="true",
        nullable=False,
    )
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoke_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    account: Mapped[Account] = relationship(
        "Account",
        back_populates="subscriptions",
    )

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, account_id={self.account_id}, plan_id={self.plan_id}, status={self.status})>"
