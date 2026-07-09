"""
test_integrity.py — Unit and integration tests for integrity verification, checksums, and retention pruning (Phase 3.4).
"""
import asyncio
import json
import shutil
import time
from pathlib import Path
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.config import settings
from app.observability.metrics import metrics_registry
from app.recovery.backup import BackupService
from app.recovery.exceptions import ArchiveCorruptedError, IntegrityVerificationError
from app.recovery.integrity import IntegrityVerifier, get_verification_state
from app.recovery.retention import RetentionPolicy, prune_backups


@pytest.fixture(autouse=True)
def isolated_backup_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure every test runs against a clean temporary backup directory."""
    b_dir = tmp_path / "test_integrity_backups"
    b_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "backup_directory", str(b_dir))
    yield b_dir
    if b_dir.exists():
        shutil.rmtree(b_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_verify_backup_success_and_state_tracking(db_session: AsyncSession, isolated_backup_dir: Path):
    """Verify clean backup passes integrity checks and records verification timestamp."""
    backup_srv = BackupService(isolated_backup_dir)
    meta = await backup_srv.create_backup(db_session)
    backup_id = meta["backup_id"]

    res = backup_srv.verify_backup(backup_id)
    assert res["status"] == "ok"
    assert res["database_valid"] is True
    assert res["configuration_valid"] is True
    assert res["checksums_valid"] is True
    assert "database.sql.gz" in res["verified_files"]

    state = get_verification_state(isolated_backup_dir)
    assert state["last_successful_verification"] is not None
    assert state["total_verifications"] == 1
    assert state["failed_verifications"] == 0


@pytest.mark.asyncio
async def test_archive_tampering_1_byte_detection(db_session: AsyncSession, isolated_backup_dir: Path):
    """Verify that tampering with even a single byte in an archive immediately raises ArchiveCorruptedError."""
    backup_srv = BackupService(isolated_backup_dir)
    meta = await backup_srv.create_backup(db_session)
    backup_id = meta["backup_id"]

    db_file = isolated_backup_dir / backup_id / "database.sql.gz"
    with open(db_file, "r+b") as f:
        data = bytearray(f.read())
        # Flip 1 byte in the middle of the archive
        idx = len(data) // 2
        data[idx] = data[idx] ^ 0xFF
        f.seek(0)
        f.write(data)

    with pytest.raises(ArchiveCorruptedError, match="Checksum mismatch"):
        backup_srv.verify_backup(backup_id)

    state = get_verification_state(isolated_backup_dir)
    assert state["last_failed_verification"] is not None
    assert state["failed_verifications"] == 1

    summary = metrics_registry.get_summary()
    assert summary.get("backup_verification_failures", 0) >= 1.0


@pytest.mark.asyncio
async def test_retention_pruning_by_count(db_session: AsyncSession, isolated_backup_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify retention policy automatically prunes oldest backups when count quota is exceeded."""
    monkeypatch.setattr(settings, "backup_max_count", 2)
    backup_srv = BackupService(isolated_backup_dir)

    # Create 3 backups sequentially with small delay to ensure distinct timestamps
    meta1 = await backup_srv.create_backup(db_session)
    await asyncio.sleep(0.01)
    meta2 = await backup_srv.create_backup(db_session)
    await asyncio.sleep(0.01)
    meta3 = await backup_srv.create_backup(db_session)

    stored = backup_srv.list_backups()
    assert len(stored) == 2, f"Expected 2 backups retained after count pruning, got {len(stored)}"
    
    retained_ids = [b["backup_id"] for b in stored]
    assert meta3["backup_id"] in retained_ids
    assert meta2["backup_id"] in retained_ids
    assert meta1["backup_id"] not in retained_ids, "Oldest backup meta1 must be pruned"


@pytest.mark.asyncio
async def test_admin_health_endpoint_backup_metadata(
    async_client: AsyncClient,
    admin_auth_headers_factory,
    db_session: AsyncSession,
    isolated_backup_dir: Path,
):
    """Verify admin /health endpoint exposes backup counts, ages, and verification timestamps."""
    headers, _ = await admin_auth_headers_factory(is_super_admin=True)
    backup_srv = BackupService(isolated_backup_dir)
    await backup_srv.create_backup(db_session)

    res = await async_client.get("/admin/health", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "backups" in data
    assert data["backups"] is not None
    assert data["backups"]["count"] == 1
    assert data["backups"]["latest_backup_age"] is not None
    assert data["backups"]["latest_backup_age"] >= 0
