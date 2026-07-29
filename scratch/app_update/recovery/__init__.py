"""
app/recovery — Disaster Recovery, Backup & Data Integrity Package (Phase 3.4).

Provides framework-independent data protection:
  - Backup creation (Database snapshots, Configuration archives, Metadata manifests)
  - Restore preview inspection
  - Integrity verification and cryptographic SHA-256 validation
  - Automated retention and pruning rules
"""
from app.recovery.exceptions import (
    RecoveryError,
    BackupError,
    RestoreError,
    IntegrityVerificationError,
    ArchiveCorruptedError,
    BackupNotFoundError,
)

__all__ = [
    "RecoveryError",
    "BackupError",
    "RestoreError",
    "IntegrityVerificationError",
    "ArchiveCorruptedError",
    "BackupNotFoundError",
]
