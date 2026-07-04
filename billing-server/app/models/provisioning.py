"""
provisioning.py — Provisioning models representing remote VPN user profiles and lifecycle state.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, Enum as SQLEnum, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref
from sqlalchemy.types import Uuid

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account


class ProvisioningState(str, Enum):
    """
    Lifecycle state of the remote VPN profile in the provisioning provider (e.g., Marzban).
    """
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"
    SYNCHRONIZED = "SYNCHRONIZED"


class ProvisioningProfile(Base, TimestampMixin):
    """
    ProvisioningProfile table.
    Stores synchronization state, remote user identifiers, and retry diagnostics for VPN providers.
    Never stores plaintext VPN credentials, VLESS URIs, or traffic logs.
    """
    __tablename__ = "provisioning_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    remote_user_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    provisioning_state: Mapped[ProvisioningState] = mapped_column(
        SQLEnum(
            ProvisioningState,
            name="provisioning_state",
            create_constraint=True,
            native_enum=True,
        ),
        nullable=False,
        default=ProvisioningState.PENDING,
        index=True,
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    account: Mapped["Account"] = relationship(
        "Account",
        backref=backref("provisioning_profile", uselist=False, cascade="all, delete-orphan"),
    )
