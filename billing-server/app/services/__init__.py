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
    SubscriptionServiceError,
    UnknownPlanError,
    DeviceLimitExceededError,
    ConnectionSignalServiceError,
    AdminSecurityError,
    AdminNotActiveError,
    InvalidAdminTokenError,
    AdminTokenExpiredError,
    MFANotImplementedYet,
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
from app.services.subscription_plan import SubscriptionPlanService
from app.services.connection_signal import ConnectionSignalService
from app.services.admin_auth import (
    AdminAuthenticationService,
    AdminAuthResult,
    AdminAuthReason,
)

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
    "SubscriptionServiceError",
    "UnknownPlanError",
    "DeviceLimitExceededError",
    "ConnectionSignalServiceError",
    "AdminSecurityError",
    "AdminNotActiveError",
    "InvalidAdminTokenError",
    "AdminTokenExpiredError",
    "MFANotImplementedYet",
    "AuthenticationService",
    "AuthenticationResult",
    "AuthenticationReason",
    "RefreshTokenService",
    "RefreshTokenResult",
    "RefreshRotationResult",
    "RefreshTokenInfo",
    "DeviceService",
    "SubscriptionPlanService",
    "ConnectionSignalService",
    "AdminAuthenticationService",
    "AdminAuthResult",
    "AdminAuthReason",
]

