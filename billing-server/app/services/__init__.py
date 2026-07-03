"""
Services package for RealityTunnel Billing/Auth API.
Encapsulates core business logic and domain services.
"""
from app.services.exceptions import (
    ServiceError,
    AuthenticationServiceError,
    AccountNotActiveError,
    JWTServiceError,
    InvalidTokenError,
    TokenExpiredError,
    InvalidSignatureError,
    InvalidIssuerError,
    InvalidAudienceError,
    TokenNotYetValidError,
    RefreshTokenServiceError,
    RefreshTokenNotFoundError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
    RefreshTokenReplayError,
    DeviceServiceError,
    DeviceOwnershipError,
    DeviceNotFoundError,
    InactiveDeviceError,
)
from app.services.authentication import (
    AuthenticationService,
    AuthenticationResult,
    AuthenticationReason,
)
from app.services.refresh_tokens import (
    RefreshTokenService,
    RefreshTokenResult,
    RefreshRotationResult,
    RefreshTokenInfo,
)
from app.services.device import DeviceService

__all__ = [
    "ServiceError",
    "AuthenticationServiceError",
    "AccountNotActiveError",
    "JWTServiceError",
    "InvalidTokenError",
    "TokenExpiredError",
    "InvalidSignatureError",
    "InvalidIssuerError",
    "InvalidAudienceError",
    "TokenNotYetValidError",
    "RefreshTokenServiceError",
    "RefreshTokenNotFoundError",
    "RefreshTokenExpiredError",
    "RefreshTokenRevokedError",
    "RefreshTokenReplayError",
    "DeviceServiceError",
    "DeviceOwnershipError",
    "DeviceNotFoundError",
    "InactiveDeviceError",
    "AuthenticationService",
    "AuthenticationResult",
    "AuthenticationReason",
    "RefreshTokenService",
    "RefreshTokenResult",
    "RefreshRotationResult",
    "RefreshTokenInfo",
    "DeviceService",
]

