"""
admin_user.py — Administrative User model representing system administrators.

Completely isolated from customer Accounts and VPN traffic tables.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import Boolean, String, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.database import Base
from app.models.base import TimestampMixin


class AdminUser(Base, TimestampMixin):
    """
    Administrative Users table.
    Stores administrative credentials (Argon2id hashes) and security flags.
    Completely decoupled from customer Account tables and JWTs.
    """
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )
    is_super_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AdminUser id={self.id} username='{self.username}' active={self.is_active} super={self.is_super_admin}>"
