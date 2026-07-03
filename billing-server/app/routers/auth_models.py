"""
auth_models.py — Transport DTOs for Authentication & Refresh API Endpoints.

Strictly isolates HTTP request/response models from internal database entities and domain models.
Enforces clean OpenAPI documentation without exposing internal dataclasses or credentials.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.security import ACCESS_TOKEN_EXPIRE_MINUTES


class LoginRequest(BaseModel):
    """Payload for POST /api/auth/login."""
    account_id: str = Field(..., description="Human-readable Account ID (e.g., RT-XXXX-XXXX)")
    master_token: str = Field(..., description="64-character hexadecimal Master Token")
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
