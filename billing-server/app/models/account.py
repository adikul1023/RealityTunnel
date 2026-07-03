"""
account.py — Account model representing user subscriptions and credentials.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, Enum as SQLEnum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base
from app.models.base import SubscriptionStatus, TimestampMixin

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.refresh_token import RefreshToken


class Account(Base, TimestampMixin):
    """
    Accounts table.
    Stores subscription state, human-readable Account ID, and hashed Master Token.
    Never stores plaintext credentials or VPN traffic logs.
    """
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    account_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    master_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    # Invariant: marzban_username is write-only from Server 1.
    # Server 1 creates/updates it via the Marzban API and never trusts values coming
    # back from Marzban to overwrite its own state.
    marzban_username: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(
            SubscriptionStatus,
            name="subscription_status",
            create_constraint=True,
            native_enum=True,
        ),
        default=SubscriptionStatus.PENDING,
        nullable=False,
        index=True,
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )

    # Relationships
    devices: Mapped[list[Device]] = relationship(
        "Device",
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        # account_id is truncated to prevent it from appearing in full in debug logs via repr().
        account_id_prefix = (self.account_id or "")[:7] + "…" if self.account_id else "N/A"
        return f"<Account(id={self.id}, account_id={account_id_prefix}, status={self.status})>"
