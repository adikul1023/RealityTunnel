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


class DeviceRevokedError(RefreshTokenServiceError):
    """
    Raised when a refresh token operation fails because the device was explicitly removed or deactivated.
    Unlike ReplayError, this does not trigger an account-wide logout.
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


class SubscriptionNotFoundError(SubscriptionServiceError):
    """Raised when a queried subscription entity does not exist."""
    pass


class InvalidSubscriptionStateError(SubscriptionServiceError):
    """Raised when attempting an invalid state transition on a subscription."""
    pass


class SubscriptionAlreadyActiveError(SubscriptionServiceError):
    """Raised when attempting to create or activate a subscription for an account that already has an active subscription."""
    pass


class SubscriptionExpiredError(SubscriptionServiceError):
    """Raised when attempting an operation on an expired subscription."""
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


# ── VPN Provisioning Domain (Phase 2.2) ─────────────────────────────────────


class ProvisioningServiceError(ServiceError):
    """Base exception for VPN provisioning orchestration and provider integration."""
    pass


class ProvisioningProviderError(ProvisioningServiceError):
    """Raised when the remote provisioning provider returns an API or business error."""
    pass


class ProvisioningConflictError(ProvisioningServiceError):
    """Raised when a provisioning operation conflicts with existing remote or local state."""
    pass


class ProvisioningUnavailableError(ProvisioningServiceError):
    """Raised when the remote provisioning provider is unreachable or offline."""
    pass


class ProvisioningSynchronizationError(ProvisioningServiceError):
    """Raised when state synchronization or reconciliation with the remote provider fails."""
    pass


class ProvisioningTimeoutError(ProvisioningServiceError):
    """Raised when an HTTP or network request to the remote provisioning provider times out."""
    pass


# ── Payment Domain & Gateway Integration Exceptions (Phase 2.3) ────────────


class PaymentServiceError(ServiceError):
    """Base exception for payment domain orchestration and gateway integration."""
    pass


class PaymentNotFoundError(PaymentServiceError):
    """Raised when a payment cannot be found or does not belong to the account."""
    pass


class PaymentOrderError(PaymentServiceError):
    """Raised when creating a payment order fails."""
    pass


class PaymentGatewayUnavailableError(PaymentServiceError):
    """Raised when the payment gateway is unreachable or offline."""
    pass


class PaymentProviderError(PaymentServiceError):
    """Raised when the payment gateway provider returns an API or business error."""
    pass



class PaymentVerificationError(PaymentServiceError):
    """Raised when payment signature verification or provider status verification fails."""
    pass


class PaymentWebhookError(PaymentServiceError):
    """Raised when processing a payment webhook fails."""
    pass


class DuplicateWebhookError(PaymentWebhookError):
    """Raised when an already processed webhook is received (handled idempotently)."""
    pass


class PaymentTimeoutError(PaymentServiceError):
    """Raised when an HTTP request to the payment gateway provider times out."""
    pass


class PaymentRefundError(PaymentServiceError):
    """Raised when attempting to refund a payment fails or is rejected by the provider."""
    pass


# ── Phase 2.4 — VPN Credential Lifecycle Exceptions ─────────────────────────


class CredentialServiceError(ServiceError):
    """Base exception for VPN credential lifecycle and client config operations."""
    pass


class CredentialNotFoundError(CredentialServiceError):
    """Raised when active VPN credentials cannot be found for an account."""
    pass


class CredentialAlreadyRevokedError(CredentialServiceError):
    """Raised when attempting to revoke credentials that are already suspended/revoked."""
    pass


class CredentialAlreadyActiveError(CredentialServiceError):
    """Raised when attempting to restore credentials that are already active."""
    pass


class CredentialRotationFailedError(CredentialServiceError):
    """Raised when regenerating or rotating credentials fails in the provider."""
    pass


