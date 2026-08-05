"""
exceptions.py — Database and repository layer custom exceptions.
Defines reusable exceptions without HTTP coupling.
"""
from __future__ import annotations
from typing import Any


class RepositoryError(Exception):
    """Base exception for repository and database operations."""
    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class InvalidCertificateError(RepositoryError):
    """Raised when an invalid certificate is provided."""
    def __init__(self, message: str = "Invalid certificate provided", detail: Any = None):
        super().__init__(message, detail)


class EntityNotFoundError(RepositoryError):
    """Raised when a queried entity does not exist in the persistence layer."""
    pass


class DuplicateEntityError(RepositoryError):
    """Raised when creating or updating an entity violates a uniqueness constraint."""
    pass


class DatabaseOperationError(RepositoryError):
    """Raised when an unhandled database or SQLAlchemy integrity error occurs."""
    pass
