"""
checksums.py — SHA-256 cryptographic checksum generators and validators.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Union

from app.recovery.exceptions import ArchiveCorruptedError, IntegrityVerificationError


def generate_file_checksum(filepath: Union[str, Path]) -> str:
    """Generate SHA-256 hexadecimal digest for a file on disk streaming in 64KB chunks."""
    path = Path(filepath)
    if not path.is_file():
        raise IntegrityVerificationError(f"Cannot compute checksum: file not found at {path}")
    
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def generate_bytes_checksum(data: bytes) -> str:
    """Generate SHA-256 hexadecimal digest for in-memory bytes."""
    return hashlib.sha256(data).hexdigest()


def verify_checksum(target: Union[str, Path, bytes], expected_checksum: str) -> bool:
    """
    Verify cryptographic SHA-256 checksum against expected hexadecimal digest.
    Raises ArchiveCorruptedError if even a single byte differs.
    """
    if isinstance(target, bytes):
        actual = generate_bytes_checksum(target)
        source_name = "in-memory data"
    else:
        path = Path(target)
        actual = generate_file_checksum(path)
        source_name = f"file '{path.name}'"

    if actual.lower() != expected_checksum.lower():
        raise ArchiveCorruptedError(
            f"Checksum mismatch for {source_name}: expected {expected_checksum.lower()}, got {actual.lower()}. "
            "Archive is corrupted or tampered with."
        )
    return True
