"""
restore.py — Restore service providing safe backup preview inspection.
"""
from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path
from typing import Any

from app.config import settings
from app.recovery.exceptions import BackupNotFoundError, RestoreError

logger = logging.getLogger(__name__)


class RestoreService:
    """Provides recovery inspection and restore preview capabilities without executing restoration."""

    def __init__(self, backup_directory: Path | str | None = None) -> None:
        self.backup_dir = Path(backup_directory or getattr(settings, "backup_directory", "./backups"))

    def _inspect_database_archive(self, db_archive: Path) -> dict[str, Any]:
        """Read schema and table metadata from database archive without altering live database."""
        if not db_archive.exists():
            return {"status": "missing", "tables": []}

        tables: list[str] = []
        row_counts: dict[str, int] = {}
        try:
            with gzip.open(db_archive, "rt", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str.startswith("-- TABLE:"):
                        tbl_name = line_str.split(":", 1)[1].strip()
                        if tbl_name not in tables:
                            tables.append(tbl_name)
                            row_counts[tbl_name] = 0
                    elif line_str.startswith("INSERT INTO") or line_str.startswith("{\"table\":"):
                        # Count row insertions
                        for tbl in tables:
                            if f"INSERT INTO {tbl}" in line_str or f"\"table\": \"{tbl}\"" in line_str:
                                row_counts[tbl] = row_counts.get(tbl, 0) + 1
                                break
            return {
                "status": "inspected",
                "table_count": len(tables),
                "tables": tables,
                "row_counts": row_counts,
            }
        except Exception as exc:
            logger.warning("Could not inspect table structure in %s: %s", db_archive.name, exc)
            return {"status": "unreadable", "error": str(exc), "tables": []}

    def restore_preview(self, backup_id: str) -> dict[str, Any]:
        """
        Allow administrators to inspect backup metadata, schema version, included tables,
        and file sizes without restoring or modifying active database state.
        """
        target_dir = self.backup_dir / backup_id
        if not target_dir.exists() or not target_dir.is_dir():
            raise BackupNotFoundError(f"Backup snapshot '{backup_id}' not found in storage.")

        meta_path = target_dir / "metadata.json"
        if not meta_path.exists():
            raise RestoreError(f"Backup snapshot '{backup_id}' is missing its metadata.json manifest.")

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as exc:
            raise RestoreError(f"Failed to read metadata manifest for '{backup_id}': {exc}") from exc

        db_archive = target_dir / "database.sql.gz"
        db_preview = self._inspect_database_archive(db_archive)

        file_sizes: dict[str, int] = {}
        for file in target_dir.iterdir():
            if file.is_file():
                file_sizes[file.name] = file.stat().st_size

        return {
            "backup_id": backup_id,
            "created_at": meta.get("created_at"),
            "postgres_revision": meta.get("postgres_revision", "unknown"),
            "git_commit_hash": meta.get("git_commit_hash"),
            "application_version": meta.get("application_version"),
            "configuration_fingerprint": meta.get("configuration_fingerprint"),
            "backup_size_bytes": meta.get("backup_size_bytes", sum(file_sizes.values())),
            "compression_algorithm": meta.get("compression_algorithm", "gzip"),
            "included_files": file_sizes,
            "database_preview": db_preview,
            "can_restore": False,
            "restore_method": "manual",
            "instructions_url": "docs/manual_recovery_runbook.md",
        }
