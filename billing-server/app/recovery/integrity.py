"""
integrity.py — Integrity verifier for backup snapshots, archives, and manifests.
"""
from __future__ import annotations

import gzip
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.recovery.checksums import verify_checksum
from app.recovery.exceptions import (
    ArchiveCorruptedError,
    BackupNotFoundError,
    IntegrityVerificationError,
)

logger = logging.getLogger(__name__)


def _update_verification_state(backup_root: Path, success: bool) -> None:
    """Persist verification timestamp and status for admin health monitoring."""
    state_file = backup_root / ".verification_state.json"
    now_iso = datetime.now(timezone.utc).isoformat()
    state: dict[str, Any] = {
        "last_successful_verification": None,
        "last_failed_verification": None,
        "total_verifications": 0,
        "failed_verifications": 0,
    }

    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state.update(json.load(f))
        except Exception:
            pass

    state["total_verifications"] = int(state.get("total_verifications", 0)) + 1
    if success:
        state["last_successful_verification"] = now_iso
    else:
        state["failed_verifications"] = int(state.get("failed_verifications", 0)) + 1
        state["last_failed_verification"] = now_iso
        try:
            from app.observability.metrics import metrics_registry
            metrics_registry.inc_counter("backup_verification_failures", 1.0)
        except Exception:
            pass

    try:
        backup_root.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as exc:
        logger.warning("Could not update verification state file %s: %s", state_file, exc)


def get_verification_state(backup_root: Path) -> dict[str, Any]:
    """Retrieve last verification timestamps and metrics for admin health endpoints."""
    state_file = backup_root / ".verification_state.json"
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_successful_verification": None,
        "last_failed_verification": None,
        "total_verifications": 0,
        "failed_verifications": 0,
    }


class IntegrityVerifier:
    """Verifies cryptographic checksums, metadata schemas, and archive structures."""

    def verify_database(self, db_archive_path: Path, expected_checksum: str) -> dict[str, Any]:
        """Verify database archive checksum and decompressibility without altering active DB."""
        if not db_archive_path.exists():
            raise IntegrityVerificationError(f"Database archive missing: {db_archive_path}")

        verify_checksum(db_archive_path, expected_checksum)

        # Verify decompressibility and schema signature
        try:
            with gzip.open(db_archive_path, "rt", encoding="utf-8") as f:
                first_chunk = f.read(1024)
                if not first_chunk or ("-- RealityTunnel Database Snapshot" not in first_chunk and "{" not in first_chunk):
                    raise ArchiveCorruptedError("Database archive header unrecognized or corrupted.")
        except Exception as exc:
            if isinstance(exc, ArchiveCorruptedError):
                raise
            raise ArchiveCorruptedError(f"Failed to decompress database archive: {exc}") from exc

        return {
            "valid": True,
            "archive": db_archive_path.name,
            "size_bytes": db_archive_path.stat().st_size,
            "checksum": expected_checksum,
        }

    def verify_configuration(self, config_archive_path: Path, expected_checksum: str) -> dict[str, Any]:
        """Verify configuration archive checksum and JSON parsing validity."""
        if not config_archive_path.exists():
            raise IntegrityVerificationError(f"Configuration archive missing: {config_archive_path}")

        verify_checksum(config_archive_path, expected_checksum)

        try:
            with gzip.open(config_archive_path, "rt", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    raise ArchiveCorruptedError("Configuration archive payload is not a valid JSON object.")
        except Exception as exc:
            if isinstance(exc, ArchiveCorruptedError):
                raise
            raise ArchiveCorruptedError(f"Failed to decompress or parse configuration archive: {exc}") from exc

        return {
            "valid": True,
            "archive": config_archive_path.name,
            "size_bytes": config_archive_path.stat().st_size,
            "checksum": expected_checksum,
        }

    def verify_metadata(self, metadata_path: Path, expected_checksum: str | None = None) -> dict[str, Any]:
        """Verify metadata manifest completeness and optional checksum."""
        if not metadata_path.exists():
            raise IntegrityVerificationError(f"Metadata manifest missing: {metadata_path}")

        if expected_checksum:
            verify_checksum(metadata_path, expected_checksum)

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as exc:
            raise IntegrityVerificationError(f"Cannot parse metadata manifest JSON: {exc}") from exc

        required_keys = {"backup_id", "created_at", "postgres_revision", "checksums", "backup_size_bytes"}
        missing = required_keys - set(meta.keys())
        if missing:
            raise IntegrityVerificationError(f"Metadata manifest missing required keys: {missing}")

        return {
            "valid": True,
            "manifest": metadata_path.name,
            "backup_id": meta["backup_id"],
            "created_at": meta["created_at"],
            "checksums": meta["checksums"],
        }

    def verify_checksums(self, manifest: dict[str, Any], backup_dir: Path) -> dict[str, Any]:
        """Verify all file checksums recorded in the manifest against disk contents."""
        checksums_map: dict[str, str] = manifest.get("checksums", {})
        if not checksums_map:
            raise IntegrityVerificationError("No file checksums declared in metadata manifest.")

        verified_files = []
        for filename, expected_hex in checksums_map.items():
            file_path = backup_dir / filename
            if not file_path.exists():
                raise ArchiveCorruptedError(f"Manifest references missing file: {filename}")
            
            # This will raise ArchiveCorruptedError immediately if 1 byte changed
            verify_checksum(file_path, expected_hex)
            verified_files.append(filename)

        return {
            "valid": True,
            "verified_files": verified_files,
            "count": len(verified_files),
        }

    def verify_backup_archive(self, backup_dir: Path) -> dict[str, Any]:
        """
        Execute full verification suite on a backup snapshot directory.
        Returns structured verification results or raises ArchiveCorruptedError/IntegrityVerificationError.
        """
        if not backup_dir.exists() or not backup_dir.is_dir():
            raise BackupNotFoundError(f"Backup directory not found: {backup_dir}")

        backup_root = backup_dir.parent
        meta_path = backup_dir / "metadata.json"
        
        try:
            meta_res = self.verify_metadata(meta_path)
            manifest = meta_res
            with open(meta_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)

            chk_res = self.verify_checksums(manifest_data, backup_dir)
            
            db_file = backup_dir / "database.sql.gz"
            if db_file.exists() and "database.sql.gz" in manifest_data.get("checksums", {}):
                self.verify_database(db_file, manifest_data["checksums"]["database.sql.gz"])

            cfg_file = backup_dir / "configuration.json.gz"
            if cfg_file.exists() and "configuration.json.gz" in manifest_data.get("checksums", {}):
                self.verify_configuration(cfg_file, manifest_data["checksums"]["configuration.json.gz"])

            _update_verification_state(backup_root, success=True)
            logger.info("Backup archive verified successfully: %s", backup_dir.name)
            return {
                "status": "ok",
                "backup_id": backup_dir.name,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "database_valid": True,
                "configuration_valid": True,
                "checksums_valid": True,
                "verified_files": chk_res["verified_files"],
            }
        except Exception as exc:
            _update_verification_state(backup_root, success=False)
            logger.error("Backup archive verification failed for %s: %s", backup_dir.name, exc)
            if isinstance(exc, (ArchiveCorruptedError, IntegrityVerificationError, BackupNotFoundError)):
                raise
            raise IntegrityVerificationError(f"Verification failed: {exc}") from exc
