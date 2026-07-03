"""
exceptions.py — Service layer exceptions.
Translates repository and domain errors into clean service exceptions without HTTP or framework coupling.
"""
from __future__ import annotations
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
