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
)
from app.services.authentication import (
    AuthenticationService,
    AuthenticationResult,
    AuthenticationReason,
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
    "AuthenticationService",
    "AuthenticationResult",
    "AuthenticationReason",
]
