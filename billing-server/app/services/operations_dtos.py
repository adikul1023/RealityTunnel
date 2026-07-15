"""
operations_dtos.py — Dedicated Data Transfer Objects for OperationsService (Phase 2A).

Enforces strict isolation between internal models/subsystems and operator-facing REST responses.
Ensures zero secret leakage and provides rich, future-proof structures.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.services.admin_dtos import AdminAccountResponse, AdminDeviceResponse
from app.services.admin_billing_dtos import (
    AdminSubscriptionDTO,
    AdminProvisioningDTO,
)
from app.services.provisioning.provider import ProvisionedUserDTO


class ComponentStatusDTO(BaseModel):
    """Detailed health status and latency probe of an individual system component."""
    status: Literal["healthy", "degraded", "offline"]
    latency_ms: int | None = None
    last_checked: datetime
    message: str | None = None


class EdgeStatusDTO(BaseModel):
    """Health status of an individual VPN gateway edge node (future-proofed multi-edge topology)."""
    name: str
    status: Literal["healthy", "degraded", "offline"]
    latency_ms: int | None = None


class InfrastructureStatusDTO(BaseModel):
    """Comprehensive status map across all core operational components and VPN edge nodes."""
    billing_api: ComponentStatusDTO
    database: ComponentStatusDTO
    marzban: ComponentStatusDTO
    xray: ComponentStatusDTO
    scheduler: ComponentStatusDTO
    redis: ComponentStatusDTO
    caddy: ComponentStatusDTO
    edges: list[EdgeStatusDTO] = Field(default_factory=list)


class UnifiedAccountDetailsDTO(BaseModel):
    """Canonical single-request operator view aggregating all 7 account facets."""
    model_config = ConfigDict(from_attributes=True)

    account: AdminAccountResponse
    subscription: AdminSubscriptionDTO | None = None
    devices: list[AdminDeviceResponse] = Field(default_factory=list)
    provisioning: AdminProvisioningDTO | None = None
    marzban: ProvisionedUserDTO | None = None
    vpn: dict[str, Any] | None = None  # Contains last_seen, last_ip, last_handshake
    usage: dict[str, Any] | None = None


class AuditEventItemDTO(BaseModel):
    """Single security and operator audit log event."""
    event_id: str
    timestamp: str
    event_type: str
    source: Literal["billing", "marzban", "scheduler", "operator", "system"]
    actor_id: str | None = None
    target_id: str | None = None
    details: dict[str, Any] | None = None
    ip_hash: str | None = None


class AuditEventCursorPageDTO(BaseModel):
    """Cursor-paginated result of audit log events."""
    items: list[AuditEventItemDTO]
    next_cursor: str | None = None
    prev_cursor: str | None = None
    has_more: bool


class DeviceRemovalResponseDTO(BaseModel):
    """Result of single device removal from an account."""
    removed: bool
    remaining_devices: int


class AdminVersionResponseDTO(BaseModel):
    """Backend version and build identifiers for immediate operator troubleshooting."""
    billing_api: str
    marzban: str | None = None
    xray: str | None = None
    sing_box_min: str
    database_schema: str
    git_commit: str
