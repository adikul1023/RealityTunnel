"""
exceptions.py — Domain exception hierarchy for Phase 3.5 Security Hardening & Production Defense.

Strictly orthogonal to authentication, billing, or provisioning logic.
"""
from __future__ import annotations


class SecurityHardeningError(Exception):
    """Base class for all security hardening and production defense exceptions."""
    def __init__(self, message: str, details: dict[str, any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TLSValidationError(SecurityHardeningError):
    """Raised when an insecure HTTP URL or invalid TLS certificate is encountered in production."""
    pass


class CSRFValidationError(SecurityHardeningError):
    """Raised when Cross-Site Request Forgery (CSRF) validation fails on browser-facing requests."""
    pass


class InputValidationError(SecurityHardeningError):
    """Raised when request payload exceeds size limits, contains malformed JSON, invalid UTF-8, or invalid UUIDs."""
    pass


class SecretRotationError(SecurityHardeningError):
    """Raised when cryptographic secret rotation fails or an invalid secret generation is accessed."""
    pass
