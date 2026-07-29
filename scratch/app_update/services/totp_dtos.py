"""
totp_dtos.py — Data Transfer Objects for Two-Factor Authentication API.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TotpSetupResponse(BaseModel):
    """Response model for POST /api/account/2fa/setup."""
    qr_data_uri: str = Field(..., description="Base64 PNG data URI for QR code rendering")
    secret: str = Field(..., description="Base32 TOTP secret shown once for manual setup")
    backup_codes: list[str] = Field(..., description="10 plaintext backup codes shown once")


class TotpStatusResponse(BaseModel):
    """Response model for GET /api/account/2fa/status."""
    enabled: bool = Field(..., description="Whether 2FA is currently active on this account")


class TotpVerificationRequest(BaseModel):
    """Payload for POST /api/account/2fa/enable and /api/account/2fa/disable."""
    code: str = Field(..., description="6-digit TOTP code or backup code")


class TotpRegenerateResponse(BaseModel):
    """Response model for POST /api/account/2fa/regenerate-backups."""
    backup_codes: list[str] = Field(..., description="10 new plaintext backup codes shown once")
