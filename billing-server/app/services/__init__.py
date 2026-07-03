"""
Services package for RealityTunnel Billing/Auth API.
Encapsulates core business logic and domain services.
"""
from app.services.exceptions import (
    ServiceError,
    AuthenticationServiceError,
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

__all__ = [
    "ServiceError",
    "AuthenticationServiceError",
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
    "AuthenticationService",
    "AuthenticationResult",
    "AuthenticationReason",
    "RefreshTokenService",
    "RefreshTokenResult",
    "RefreshRotationResult",
    "RefreshTokenInfo",
]
