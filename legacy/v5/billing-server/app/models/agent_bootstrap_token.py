"""
agent_bootstrap_token.py - Model for one-time agent bootstrap provisioning tokens.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin

class AgentBootstrapToken(Base, TimestampMixin):
    """
    AgentBootstrapToken table.
    Stores one-time tokens used by VPNHood nodes to bootstrap their identity.
    """
    __tablename__ = "agent_bootstrap_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False, default="vpnhood_node_bootstrap")
