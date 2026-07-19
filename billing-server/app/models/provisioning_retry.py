"""
provisioning_retry.py — Provisioning retry item entity representing transient failure queue in Phase 2.6.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account


class RetryItemStatus(str, Enum):
    """
    Status of a transient provisioning retry item.
    """
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProvisioningAction(str, Enum):
    """
    Action to retry.
    """
    PROVISION = "PROVISION"
    TERMINATE = "TERMINATE"
    SUSPEND = "SUSPEND"


class ProvisioningRetryItem(Base, TimestampMixin):
    """
    ProvisioningRetryItem table (provisioning_retry_queue).
    Stores transient provisioning failures (timeouts, HTTP 500/502/503/504) for automatic
    retry with exponential backoff.
    """
    __tablename__ = "provisioning_retry_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    action: Mapped[ProvisioningAction] = mapped_column(
        SQLEnum(ProvisioningAction, name="provisioning_action"),
        default=ProvisioningAction.PROVISION,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    last_error: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    status: Mapped[RetryItemStatus] = mapped_column(
        SQLEnum(RetryItemStatus, name="retry_item_status"),
        default=RetryItemStatus.PENDING,
        nullable=False,
        index=True,
    )

    account: Mapped["Account"] = relationship("Account")

    def __repr__(self) -> str:
        return (
            f"<ProvisioningRetryItem(id={self.id}, account_id={self.account_id}, "
            f"plan_id='{self.plan_id}', attempt_count={self.attempt_count}, status={self.status.value})>"
        )
