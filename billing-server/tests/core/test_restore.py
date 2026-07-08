"""
test_restore.py — Unit tests for RestoreService preview inspection (Phase 3.4).
"""
import shutil
from pathlib import Path
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.recovery.backup import BackupService
from app.recovery.exceptions import BackupNotFoundError, RestoreError
from app.recovery.restore import RestoreService


@pytest.fixture(autouse=True)
def isolated_backup_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure every test runs against a clean temporary backup directory."""
    b_dir = tmp_path / "test_restore_backups"
    b_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "backup_directory", str(b_dir))
    yield b_dir
    if b_dir.exists():
        shutil.rmtree(b_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_restore_preview_inspection(db_session: AsyncSession, isolated_backup_dir: Path):
    """Verify restore_preview accurately reports schema metadata and file sizes without altering DB."""
    backup_srv = BackupService(isolated_backup_dir)
    meta = await backup_srv.create_backup(db_session)
    backup_id = meta["backup_id"]

    restore_srv = RestoreService(isolated_backup_dir)
    preview = restore_srv.restore_preview(backup_id)

    assert preview["backup_id"] == backup_id
    assert preview["can_restore"] is False
    assert preview["restore_method"] == "manual"
    assert preview["instructions_url"] == "docs/manual_recovery_runbook.md"
    assert preview["postgres_revision"] == meta["postgres_revision"]
    assert preview["backup_size_bytes"] == meta["backup_size_bytes"]
    assert "database.sql.gz" in preview["included_files"]
    assert "configuration.json.gz" in preview["included_files"]
    assert preview["database_preview"]["status"] == "inspected"
    assert preview["database_preview"]["table_count"] > 0


def test_restore_preview_missing_backup(isolated_backup_dir: Path):
    """Verify requesting preview for non-existent backup raises BackupNotFoundError."""
    restore_srv = RestoreService(isolated_backup_dir)
    with pytest.raises(BackupNotFoundError):
        restore_srv.restore_preview("backup_invalid_nonexistent")
