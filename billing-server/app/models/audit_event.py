"""
audit_event.py — Audit event model for durable security audit logging (Phase 3.0.5).

Provides append-only database storage for security-critical audit events.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class AuditEvent(Base, TimestampMixin):
    """
    Durable audit event record stored in the database.
    Provides append-only immutability through database constraints.
    """
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Indexes for common query patterns
    __table_args__ = (
        Index("idx_audit_events_timestamp_type", "timestamp", "event_type"),
        Index("idx_audit_events_actor_target", "actor_id", "target_id"),
    )
