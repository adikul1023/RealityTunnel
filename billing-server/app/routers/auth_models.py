"""
auth_models.py — Transport DTOs for Authentication & Refresh API Endpoints.

Strictly isolates HTTP request/response models from internal database entities and domain models.
Enforces clean OpenAPI documentation without exposing internal dataclasses or credentials.
"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, SecretStr

from app.models import SubscriptionStatus
from app.security import ACCESS_TOKEN_EXPIRE_MINUTES


class LoginRequest(BaseModel):
    """Payload for POST /api/auth/login."""
    account_id: str = Field(..., description="Human-readable Account ID (e.g., RT-XXXX-XXXX)")
    master_token: SecretStr = Field(
        ...,
        description="64-character hexadecimal Master Token",
        json_schema_extra={"writeOnly": True},
    )
    device_guid: str = Field(..., description="Unique hardware or installation identifier")


class RefreshRequest(BaseModel):
    """Payload for POST /api/auth/refresh."""
    refresh_token: str = Field(..., description="Active 64-character hexadecimal refresh token")


class LogoutRequest(BaseModel):
    """Payload for POST /api/auth/logout and POST /api/auth/logout-all."""
    refresh_token: str = Field(..., description="Refresh token identifying the session or account to revoke")


class LoginResponse(BaseModel):
    """Successful authentication token pair response."""
    access_token: str = Field(..., description="Short-lived Ed25519 signed Access JWT")
    refresh_token: str = Field(..., description="Long-lived 256-bit CSPRNG refresh token")
    token_type: str = Field(default="Bearer", description="HTTP authorization scheme")
    expires_in: int = Field(
        default=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        description="Access token validity duration in seconds",
    )


class RefreshResponse(BaseModel):
    """Successful refresh token rotation response."""
    access_token: str = Field(..., description="New short-lived Ed25519 signed Access JWT")
    refresh_token: str = Field(..., description="New rotated long-lived refresh token")
    token_type: str = Field(default="Bearer", description="HTTP authorization scheme")
    expires_in: int = Field(
        default=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        description="Access token validity duration in seconds",
    )


class SuccessResponse(BaseModel):
    """Generic success confirmation for logout operations."""
    success: bool = Field(default=True, description="Indicates operation completed successfully")


class AccountMeResponse(BaseModel):
    """
    Response model for GET /api/auth/me returning non-sensitive account identity.
    Strictly omits credentials, tokens, hashes, database UUIDs, and internal metadata.
    """
    account_id: str = Field(..., description="Human-readable Account ID (e.g., RT-XXXX-XXXX)")
    status: SubscriptionStatus = Field(..., description="Current subscription lifecycle status")
    subscription_expires_at: datetime | None = Field(
        None, description="Subscription expiration timestamp (UTC)"
    )


class DeviceLimitErrorResponse(BaseModel):
    """
    Error response returned when device registration exceeds the subscription plan limit (HTTP 403).
    """
    detail: str = Field(default="Device limit reached", description="Error explanation")
    plan: str = Field(..., description="Subscription plan identifier")
    current_devices: int = Field(..., description="Current number of active devices")
    max_devices: int = Field(..., description="Maximum allowed devices for the plan")


class InactiveDeviceErrorResponse(BaseModel):
    """
    Error response returned when attempting to login with a deactivated device (HTTP 403).
    """
    detail: str = Field(..., description="Instructions to reactivate the device or register a new one")

