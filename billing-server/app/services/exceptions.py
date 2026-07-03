"""
exceptions.py — Service layer exceptions.
Translates repository and domain errors into clean service exceptions without HTTP or framework coupling.
"""
from __future__ import annotations
import uuid
from typing import Any


class ServiceError(Exception):
    """Base exception for service layer operations."""
    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class AuthenticationServiceError(ServiceError):
    """Raised when an unexpected error or database failure occurs during authentication."""
    pass


class AccountNotActiveError(AuthenticationServiceError):
    """Raised when an authenticated account is deleted, suspended, pending, expired, or otherwise inactive during token validation."""
    pass



class JWTServiceError(ServiceError):
    """Base exception for JWT service and cryptographic validation operations."""
    pass


class InvalidTokenError(JWTServiceError):
    """Raised when a JWT is malformed, missing required claims, or fails general validation."""
    pass


class TokenExpiredError(InvalidTokenError):
    """Raised when a JWT has expired (exp claim is in the past)."""
    pass


class InvalidSignatureError(InvalidTokenError):
    """Raised when a JWT cryptographic signature is invalid or tampered with."""
    pass


class InvalidIssuerError(InvalidTokenError):
    """Raised when a JWT iss claim does not match the expected issuer."""
    pass


class InvalidAudienceError(InvalidTokenError):
    """Raised when a JWT aud claim does not match the expected audience."""
    pass


class TokenNotYetValidError(InvalidTokenError):
    """Raised when a JWT is used before its Not Before (nbf) timestamp."""
    pass


class RefreshTokenServiceError(ServiceError):
    """Base exception for refresh token rotation and lifecycle operations."""
    def __init__(
        self,
        message: str,
        *,
        account_id: uuid.UUID | None = None,
        device_guid: str | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.account_id = account_id
        self.device_guid = device_guid


class RefreshTokenNotFoundError(RefreshTokenServiceError):
    """Raised when an unknown or unrecognized refresh token string is presented."""
    pass


class RefreshTokenExpiredError(RefreshTokenServiceError):
    """Raised when a refresh token has passed its expiration timestamp."""
    pass


class RefreshTokenRevokedError(RefreshTokenServiceError):
    """Raised when a refresh token operation fails because the token is revoked without replay evidence."""
    pass


class RefreshTokenReplayError(RefreshTokenServiceError):
    """
    Raised when replay attack evidence is detected (attempting to use an already-revoked valid token).
    Triggers immediate account-wide session revocation.
    """
    pass


class DeviceServiceError(ServiceError):
    """Base exception for device registration and management operations."""
    pass


class DeviceOwnershipError(DeviceServiceError):
    """Raised when attempting to register or manipulate a device GUID owned by another account."""
    pass


class DeviceNotFoundError(DeviceServiceError):
    """Raised when a requested device GUID does not exist."""
    pass


class InactiveDeviceError(DeviceServiceError):
    """Raised when attempting an operation on a deactivated device or deactivating an already inactive device."""
    pass


class SubscriptionServiceError(ServiceError):
    """Base exception for subscription plans and policy enforcement."""
    pass


class UnknownPlanError(SubscriptionServiceError):
    """Raised when an unrecognized plan_id is encountered."""
    pass


class DeviceLimitExceededError(DeviceServiceError):
    """
    Raised when an account attempts to register a new device beyond its subscription plan limit.
    """
    def __init__(self, current_device_count: int, max_devices: int, plan_id: str):
        message = f"Device limit reached for plan '{plan_id}': {current_device_count}/{max_devices} devices registered."
        detail = {
            "detail": "Device limit reached",
            "plan": plan_id,
            "current_devices": current_device_count,
            "max_devices": max_devices,
        }
        super().__init__(message, detail=detail)
        self.current_device_count = current_device_count
        self.max_devices = max_devices
        self.plan_id = plan_id


class ConnectionSignalServiceError(ServiceError):
    """Raised when an error occurs while recording or querying connection security signals."""
    pass


class AdminSecurityError(ServiceError):
    """Base exception for administrative security operations."""
    pass


class AdminNotActiveError(AdminSecurityError):
    """Raised when attempting to authenticate an inactive administrative account."""
    pass


class InvalidAdminTokenError(AdminSecurityError):
    """Raised when an admin JWT signature, issuer, or audience is invalid."""
    pass


class AdminTokenExpiredError(AdminSecurityError):
    """Raised when an admin JWT has passed its expiration timestamp."""
    pass


class MFANotImplementedYet(AdminSecurityError):
    """
    Raised when attempting to authenticate an administrative account with MFA enabled.
    Intentionally blocks future rollout rather than silently bypassing MFA.
    See docs/adr/ADR-001-mfa-guard-fail-closed.md for the design rationale.
    """
    pass


# ── Admin Account Management ────────────────────────────────────────────────


class AdminServiceError(ServiceError):
    """Base exception for administrative account management operations."""
    pass


class AdminAccountNotFoundError(AdminServiceError):
    """Raised when an account lookup by account_id finds no matching row."""
    pass
