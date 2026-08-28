"""
agent_node.py - Model representing a VPN node (VPNHood agent).
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.agent_certificate import AgentCertificate
    from app.models.agent_session import AgentSession


class AgentNode(Base, TimestampMixin):
    """
    AgentNode table.
    Represents an authenticated VPNHood node within the control plane.
    """
    __tablename__ = "agent_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    machine_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    os_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vpnhood_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    public_ip: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    config_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    certificates: Mapped[list["AgentCertificate"]] = relationship(
        "AgentCertificate", back_populates="node", cascade="all, delete-orphan"
    )

    sessions: Mapped[list["AgentSession"]] = relationship(
        "AgentSession", back_populates="node", cascade="all, delete-orphan"
    )
