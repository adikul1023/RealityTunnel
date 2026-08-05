"""
refresh_token.py — RefreshToken model supporting Refresh Token Rotation (RTR).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, Boolean, ForeignKey, func, text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base
from app.models.base import RevocationReason

if TYPE_CHECKING:
    from app.models.account import Account


class RefreshToken(Base):
    """
    Refresh Tokens table.
    Stores SHA-256 hashed refresh tokens for secure session rotation.
    Tokens are never stored in plaintext.
    """
    __tablename__ = "refresh_tokens"

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
        String(64), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    revoked_reason: Mapped[RevocationReason | None] = mapped_column(
        Enum(RevocationReason, name="revocation_reason_enum"), nullable=True, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    account: Mapped[Account] = relationship(
        "Account", back_populates="refresh_tokens"
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, account_id={self.account_id}, revoked={self.is_revoked})>"
