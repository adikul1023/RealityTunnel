"""
device_models.py — Transport DTOs for Device Management API (Phase 1.4.2).

Strictly isolates HTTP request/response schemas from internal database entities.
Never exposes database UUIDs, foreign keys, or internal IDs.
"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DeviceResponse(BaseModel):
    """Public representation of a registered client device."""
    model_config = ConfigDict(from_attributes=True)

    device_guid: str = Field(..., description="Unique hardware or installation identifier")
    friendly_name: str | None = Field(None, description="User-assigned friendly device name")
    first_seen_at: datetime = Field(..., description="Initial registration timestamp (UTC)")
    last_seen_at: datetime = Field(..., description="Most recent activity timestamp (UTC)")
    is_active: bool = Field(..., description="Whether device is active or soft-deactivated")


class DeviceListResponse(BaseModel):
    """List of devices owned by the authenticated account."""
    devices: list[DeviceResponse] = Field(..., description="List of registered client devices")


class RenameDeviceRequest(BaseModel):
    """Payload for PATCH /api/devices/{device_guid} to update friendly name."""
    friendly_name: str = Field(..., description="New friendly name for the device")


class RegisterDeviceRequest(BaseModel):
    """Payload for POST /api/devices to register a client device."""
    device_guid: str = Field(..., description="Unique hardware or installation identifier")
    friendly_name: str | None = Field(None, description="Optional user-assigned friendly device name")


class SuccessResponse(BaseModel):
    """Generic success confirmation for device operations."""
    success: bool = Field(default=True, description="Indicates operation completed successfully")
    message: str | None = Field(default=None, description="Optional informational message")


class DeviceStatusResponse(BaseModel):
    """Real-time presence and status heartbeat response for a client device."""
    active: bool = Field(..., description="Whether device is registered and active under the current account")
    reason: str | None = Field(default=None, description="Revocation reason when active is false")
    server_time: datetime = Field(..., description="Current server UTC timestamp")
    heartbeat_interval: int = Field(default=60, description="Recommended heartbeat check interval in seconds")
    heartbeat_jitter: int = Field(default=10, description="Random jitter in seconds to apply to heartbeat interval")

