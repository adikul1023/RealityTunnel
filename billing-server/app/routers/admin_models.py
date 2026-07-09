"""
admin_models.py — Transport DTOs for Administrative Authentication Endpoints.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, SecretStr
from app.security.admin_jwt import ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES


class AdminLoginRequest(BaseModel):
    """Payload for POST /api/admin/login."""
    username: str = Field(..., description="Administrative username")
    password: SecretStr = Field(
        ...,
        description="Administrative human-generated password",
        json_schema_extra={"writeOnly": True},
    )


class AdminLoginResponse(BaseModel):
    """Successful administrative authentication response."""
    access_token: str = Field(..., description="Short-lived Ed25519 signed Admin Access JWT")
    token_type: str = Field(default="Bearer", description="HTTP authorization scheme")
    expires_in: int = Field(
        default=ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        description="Access token validity duration in seconds",
    )
    username: str = Field(..., description="Administrative username")
    role: str = Field(..., description="Administrative role")


class AdminProfileResponse(BaseModel):
    """Payload for GET /api/admin/me."""
    id: str = Field(..., description="Admin UUID")
    username: str = Field(..., description="Administrative username")
    is_active: bool = Field(..., description="Whether the account is active")
    is_super_admin: bool = Field(..., description="Whether the account has super admin privileges")
    mfa_enabled: bool = Field(..., description="Whether MFA is enabled on this account")
