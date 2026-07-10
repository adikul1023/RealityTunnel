"""
exchange_token.py — Single-use ExchangeToken model for web-to-app authentication handoff.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, Boolean, ForeignKey, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base

if TYPE_CHECKING:
    from app.models.account import Account


class ExchangeToken(Base):
    """
    Exchange Tokens table.
    Stores short-lived, single-use exchange tokens for secure web-to-client handoff.
    Tokens are stored as SHA-256 hashes and atomically invalidated upon redemption.
    """
    __tablename__ = "exchange_tokens"

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
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    is_redeemed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    is_initial_provisioning: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    account: Mapped[Account] = relationship(
        "Account"
    )

    def __repr__(self) -> str:
        return f"<ExchangeToken(id={self.id}, account_id={self.account_id}, redeemed={self.is_redeemed})>"
