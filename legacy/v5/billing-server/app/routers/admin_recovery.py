"""
admin_recovery.py — Administrative router for disaster recovery, backups, and integrity verification.
"""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_admin, require_super_admin
from app.models.admin_user import AdminUser
from app.rate_limit import require_rate_limit
from app.recovery.backup import BackupService
from app.recovery.exceptions import (
    ArchiveCorruptedError,
    BackupError,
    BackupNotFoundError,
    IntegrityVerificationError,
    RestoreError,
)
from app.recovery.restore import RestoreService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/recovery",
    tags=["Admin Disaster Recovery"],
    dependencies=[Depends(require_rate_limit("admin_endpoints"))],
)


def _handle_recovery_error(exc: Exception, operation: str) -> None:
    if isinstance(exc, BackupNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    if isinstance(exc, (ArchiveCorruptedError, IntegrityVerificationError)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message)
    if isinstance(exc, (BackupError, RestoreError)):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message)
    logger.error("Unexpected error during recovery operation '%s': %s", operation, exc)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal recovery error")


@router.post(
    "/backups",
    summary="Create data backup snapshot",
    status_code=status.HTTP_201_CREATED,
)
async def create_backup_snapshot(
    session: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(require_super_admin),
) -> dict[str, Any]:
    """Trigger immediate backup creation of database, configuration, and metadata."""
    try:
        service = BackupService()
        return await service.create_backup(session)
    except Exception as exc:
        _handle_recovery_error(exc, "create_backup_snapshot")


@router.get(
    "/backups",
    summary="List stored backup snapshots",
)
async def list_stored_backups(
    _admin: AdminUser = Depends(get_current_admin),
) -> list[dict[str, Any]]:
    """Return sorted list of stored backup snapshots with metadata."""
    try:
        service = BackupService()
        return service.list_backups()
    except Exception as exc:
        _handle_recovery_error(exc, "list_stored_backups")


@router.get(
    "/backups/{backup_id}/preview",
    summary="Inspect restore preview without restoring",
)
async def get_restore_preview(
    backup_id: str,
    _admin: AdminUser = Depends(get_current_admin),
) -> dict[str, Any]:
    """Inspect backup metadata, schema version, included tables, and sizes without executing restoration."""
    try:
        service = RestoreService()
        return service.restore_preview(backup_id)
    except Exception as exc:
        _handle_recovery_error(exc, "get_restore_preview")


@router.post(
    "/backups/{backup_id}/verify",
    summary="Execute integrity and SHA-256 checksum verification",
)
async def verify_backup_integrity(
    backup_id: str,
    _admin: AdminUser = Depends(require_super_admin),
) -> dict[str, Any]:
    """Verify cryptographic SHA-256 checksums and archive decompressibility."""
    try:
        service = BackupService()
        return service.verify_backup(backup_id)
    except Exception as exc:
        _handle_recovery_error(exc, "verify_backup_integrity")


@router.post(
    "/prune",
    summary="Trigger manual retention pruning",
)
async def prune_stored_backups(
    _admin: AdminUser = Depends(require_super_admin),
) -> dict[str, Any]:
    """Manually prune expired and over-quota backup snapshots."""
    try:
        service = BackupService()
        deleted = service.delete_expired_backups()
        return {"status": "ok", "deleted_count": len(deleted), "deleted_backups": deleted}
    except Exception as exc:
        _handle_recovery_error(exc, "prune_stored_backups")
