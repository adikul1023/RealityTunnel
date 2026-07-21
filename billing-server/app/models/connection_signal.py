"""
connection_signal.py — Connection Signal model tracking authentication & device lifecycle events.

Phase 1.4.4: Provides structured security event logging for future fraud detection and security analytics.
Strictly avoids storing secrets (JWTs, Master Tokens, Refresh Tokens, hashes, or passwords).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base

if TYPE_CHECKING:
    from app.models.account import Account


class ConnectionEventType(str, enum.Enum):
    """
    Enum representing types of recorded security events.
    """
    LOGIN = "LOGIN"
    REFRESH = "REFRESH"
    LOGOUT = "LOGOUT"
    LOGOUT_ALL = "LOGOUT_ALL"
    DEVICE_REGISTER = "DEVICE_REGISTER"
    DEVICE_RENAME = "DEVICE_RENAME"
    DEVICE_DEACTIVATE = "DEVICE_DEACTIVATE"
    DEVICE_REACTIVATE = "DEVICE_REACTIVATE"
    DEVICE_DELETE = "DEVICE_DELETE"


class ConnectionSignal(Base):
    """
    Connection Signals table.
    Records authentication and device management events for security monitoring and analytics.
    """
    __tablename__ = "connection_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    device_guid: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    event_type: Mapped[ConnectionEventType] = mapped_column(
        SQLEnum(
            ConnectionEventType,
            name="connection_event_type",
            create_constraint=True,
            native_enum=True,
        ),
        nullable=False,
        index=True,
    )
    source_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    success: Mapped[bool] = mapped_column(
        Boolean(),
        default=True,
        server_default=text("true"),
        nullable=False,
    )

    # Relationships
    account: Mapped[Account | None] = relationship("Account")

    def __repr__(self) -> str:
        return (
            f"<ConnectionSignal(id={self.id}, account_id={self.account_id}, "
            f"event_type={self.event_type}, success={self.success}, occurred_at={self.occurred_at})>"
        )
