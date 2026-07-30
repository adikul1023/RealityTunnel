"""
auth_models.py — Transport DTOs for Authentication & Refresh API Endpoints.

Strictly isolates HTTP request/response models from internal database entities and domain models.
Enforces clean OpenAPI documentation without exposing internal dataclasses or credentials.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, SecretStr

from app.models import AccountStatus
from app.security import ACCESS_TOKEN_EXPIRE_MINUTES


class ClientType(str, Enum):
    """Type of client initiating authentication or exchange requests."""
    DESKTOP = "desktop"
    WEB = "web"
    ANDROID = "android"
    IOS = "ios"
    LINUX = "linux"


class LoginRequest(BaseModel):
    """Payload for POST /api/auth/login."""
    account_id: str = Field(..., description="Human-readable Account ID (e.g., RT-XXXX-XXXX)")
    master_token: SecretStr = Field(
        ...,
        description="64-character hexadecimal Master Token",
        json_schema_extra={"writeOnly": True},
    )
    device_guid: str = Field(..., description="Unique hardware or installation identifier")
    client_type: ClientType = Field(default=ClientType.DESKTOP,
        description="Type of client initiating login ('desktop', 'web', 'android', 'ios', 'linux')",
    )
    two_fa_code: str | None = Field(
        default=None,
        description="Optional 6-digit TOTP code or backup code, required when Two-Factor Authentication is enabled",
    )


class LoginChallengeResponse(BaseModel):
    """Response returned when Two-Factor Authentication is required to complete login (HTTP 401)."""
    detail: str = Field(default="Two-factor authentication required")
    requires_2fa: bool = Field(default=True, description="Indicates TOTP code must be provided to proceed")


class RegisterAccountRequest(BaseModel):
    """Payload for POST /api/auth/register."""
    plan_id: str = Field(default="free", description="Initial subscription plan ID")


class RegisterAccountResponse(BaseModel):
    """Response for POST /api/auth/register containing one-time display credentials."""
    account_id: str = Field(..., description="Public human-readable Account ID (e.g. RT-XXXX-XXXX)")
    master_token: str = Field(..., description="Secret Master Token — shown only once")


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
    status: AccountStatus = Field(..., description="Current subscription lifecycle status")
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


class ExchangeRequest(BaseModel):
    """Payload for POST /api/auth/exchange."""
    exchange_token: str = Field(..., description="Single-use exchange token from web redirect")
    device_guid: str = Field(..., description="Unique hardware or installation identifier")
    client_type: ClientType = Field(default=ClientType.DESKTOP,
        description="Type of client initiating login ('desktop', 'web', 'android', 'ios', 'linux')",
    )


class ExchangeResponse(BaseModel):
    """Successful exchange token redemption response. NEVER returns Master Token."""
    access_token: str = Field(..., description="Short-lived Ed25519 signed Access JWT")
    refresh_token: str = Field(..., description="Long-lived 256-bit CSPRNG refresh token")
    token_type: str = Field(default="Bearer", description="HTTP authorization scheme")
    expires_in: int = Field(
        default=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        description="Access token validity duration in seconds",
    )
    is_initial_provisioning: bool = Field(
        default=False,
        description="Indicates whether this account was just provisioned for the first time",
    )

