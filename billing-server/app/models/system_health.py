"""
system_health.py — System health status entity representing generic operational checks in Phase 2.6.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class SystemHealthStatus(Base, TimestampMixin):
    """
    SystemHealthStatus table (system_health_status).
    Stores generic operational health checks for third-party providers (e.g., Marzban, Razorpay).
    Never stores plaintext API keys, tokens, or webhook secrets.
    """
    __tablename__ = "system_health_status"

    component_key: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # "ok" or "degraded"
    message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<SystemHealthStatus(component_key='{self.component_key}', "
            f"status='{self.status}', last_checked_at='{self.last_checked_at}')>"
        )
