"""
exceptions.py — Domain exceptions for disaster recovery and data protection.
"""
from __future__ import annotations


class RecoveryError(Exception):
    """Base exception for all recovery and data protection operations."""
    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class BackupError(RecoveryError):
    """Raised when backup snapshot creation fails."""
    pass


class RestoreError(RecoveryError):
    """Raised when restoration or restore preview inspection fails."""
    pass


class IntegrityVerificationError(RecoveryError):
    """Raised when backup archive verification fails."""
    pass


class ArchiveCorruptedError(IntegrityVerificationError):
    """Raised when an archive fails cryptographic checksum validation (even one byte differs)."""
    pass


class BackupNotFoundError(RecoveryError):
    """Raised when the requested backup snapshot ID is not found on storage."""
    pass
