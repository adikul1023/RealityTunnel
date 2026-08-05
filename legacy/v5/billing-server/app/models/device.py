"""
device.py — Device model tracking active client installations per account.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, Boolean, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base

if TYPE_CHECKING:
    from app.models.account import Account


class Device(Base):
    """
    Devices table.
    Tracks registered client instances under each account.
    Enforces unique device_guid globally across all accounts.
    """
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_guid: Mapped[str] = mapped_column(
        String(64), index=True, unique=True, nullable=False
    )
    friendly_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(),
        default=True,
        server_default=text("true"),
        nullable=False,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    account: Mapped[Account] = relationship(
        "Account", back_populates="devices"
    )

    def __repr__(self) -> str:
        return f"<Device(id={self.id}, account_id={self.account_id}, guid={self.device_guid}, active={self.is_active})>"
