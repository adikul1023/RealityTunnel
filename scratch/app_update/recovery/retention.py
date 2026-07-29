"""
retention.py — Automated retention policies and pruning rules for backup snapshots.
"""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.recovery.exceptions import RecoveryError

logger = logging.getLogger(__name__)


@dataclass
class RetentionPolicy:
    retention_days: int = 30
    max_count: int = 50
    max_storage_bytes: int = 1024 * 1024 * 1024  # 1 GB default

    @classmethod
    def from_settings(cls, settings) -> "RetentionPolicy":
        return cls(
            retention_days=getattr(settings, "backup_retention_days", 30),
            max_count=getattr(settings, "backup_max_count", 50),
            max_storage_bytes=getattr(settings, "backup_max_storage_mb", 1024) * 1024 * 1024,
        )


def _get_backup_size_and_time(backup_path: Path) -> tuple[int, datetime, str]:
    """Helper to read size, created_at timestamp, and backup_id from backup snapshot directory or file."""
    total_size = 0
    created_at = datetime.now(timezone.utc)
    backup_id = backup_path.name

    if backup_path.is_dir():
        for file in backup_path.rglob("*"):
            if file.is_file():
                total_size += file.stat().st_size
        
        meta_path = backup_path / "metadata.json"
        if meta_path.is_file():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    if "backup_id" in meta:
                        backup_id = str(meta["backup_id"])
                    if "created_at" in meta:
                        # Parse ISO UTC string
                        ts_str = str(meta["created_at"])
                        if ts_str.endswith("Z"):
                            ts_str = ts_str[:-1] + "+00:00"
                        created_at = datetime.fromisoformat(ts_str)
                    if "backup_size_bytes" in meta and isinstance(meta["backup_size_bytes"], (int, float)):
                        total_size = int(meta["backup_size_bytes"])
            except Exception as exc:
                logger.warning("Failed to parse metadata in backup %s during retention check: %s", backup_path.name, exc)
    elif backup_path.is_file():
        total_size = backup_path.stat().st_size
        mtime = backup_path.stat().st_mtime
        created_at = datetime.fromtimestamp(mtime, tz=timezone.utc)

    return total_size, created_at, backup_id


def prune_backups(backup_dir: Path, policy: RetentionPolicy) -> list[str]:
    """
    Enforces retention rules:
      1. Prunes backups older than retention_days.
      2. Prunes oldest backups exceeding max_count quota.
      3. Prunes oldest backups exceeding max_storage_bytes quota.
    Returns list of deleted backup IDs.
    """
    if not backup_dir.exists() or not backup_dir.is_dir():
        return []

    backups: list[tuple[Path, int, datetime, str]] = []
    for item in backup_dir.iterdir():
        if item.name.startswith("backup_") or (item.is_dir() and (item / "metadata.json").exists()):
            size, created_at, b_id = _get_backup_size_and_time(item)
            backups.append((item, size, created_at, b_id))

    if not backups:
        return []

    # Sort newest first
    backups.sort(key=lambda x: x[2], reverse=True)

    now = datetime.now(timezone.utc)
    cutoff_date = now - timedelta(days=policy.retention_days)

    deleted_ids: list[str] = []
    retained: list[tuple[Path, int, datetime, str]] = []

    # 1. Prune by age
    for item_path, size, created_at, b_id in backups:
        if created_at < cutoff_date:
            try:
                if item_path.is_dir():
                    shutil.rmtree(item_path)
                else:
                    item_path.unlink()
                deleted_ids.append(b_id)
                logger.info("Pruned expired backup %s (created %s)", b_id, created_at.isoformat())
            except Exception as exc:
                logger.error("Failed to delete expired backup %s: %s", b_id, exc)
        else:
            retained.append((item_path, size, created_at, b_id))

    # 2. Prune by count quota (retained is already newest first)
    while len(retained) > policy.max_count:
        item_path, size, created_at, b_id = retained.pop()  # Remove oldest from end
        try:
            if item_path.is_dir():
                shutil.rmtree(item_path)
            else:
                item_path.unlink()
            deleted_ids.append(b_id)
            logger.info("Pruned over-quota backup %s (exceeded max_count=%d)", b_id, policy.max_count)
        except Exception as exc:
            logger.error("Failed to delete over-quota backup %s: %s", b_id, exc)

    # 3. Prune by storage size quota
    total_retained_bytes = sum(x[1] for x in retained)
    while total_retained_bytes > policy.max_storage_bytes and len(retained) > 1:
        item_path, size, created_at, b_id = retained.pop()
        try:
            if item_path.is_dir():
                shutil.rmtree(item_path)
            else:
                item_path.unlink()
            deleted_ids.append(b_id)
            total_retained_bytes -= size
            logger.info("Pruned backup %s to satisfy storage quota (%d bytes > %d max)", b_id, total_retained_bytes + size, policy.max_storage_bytes)
        except Exception as exc:
            logger.error("Failed to delete backup %s during storage quota pruning: %s", b_id, exc)

    return deleted_ids
