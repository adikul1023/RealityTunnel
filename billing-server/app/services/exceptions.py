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
