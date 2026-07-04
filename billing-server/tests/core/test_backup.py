"""
test_backup.py — Unit and integration tests for BackupService (Phase 3.4).
"""
import asyncio
import json
import logging
import shutil
from pathlib import Path
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.observability.metrics import metrics_registry
from app.recovery.backup import BackupService, get_compressor
from app.recovery.exceptions import BackupError


@pytest.fixture(autouse=True)
def isolated_backup_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure every test runs against a clean temporary backup directory."""
    b_dir = tmp_path / "test_backups"
    b_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "backup_directory", str(b_dir))
    yield b_dir
    if b_dir.exists():
        shutil.rmtree(b_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_create_backup_success_and_metrics(db_session: AsyncSession, isolated_backup_dir: Path):
    """Verify complete backup creation creates valid archives and increments Prometheus metrics."""
    service = BackupService(isolated_backup_dir)
    meta = await service.create_backup(db_session)

    assert "backup_id" in meta
    assert "created_at" in meta
    assert "checksums" in meta
    assert "backup_size_bytes" in meta
    assert meta["backup_size_bytes"] > 0

    backup_id = meta["backup_id"]
    target_dir = isolated_backup_dir / backup_id
    assert target_dir.exists()
    assert (target_dir / "metadata.json").exists()
    assert (target_dir / "metadata.json.sha256").exists()
    assert (target_dir / "database.sql.gz").exists()
    assert (target_dir / "configuration.json.gz").exists()

    # Verify Prometheus metrics
    summary = metrics_registry.get_summary()
    assert summary.get("backup_success_total", 0) >= 1.0
    assert summary.get("backup_size_bytes", 0) == float(meta["backup_size_bytes"])


@pytest.mark.asyncio
async def test_zero_secret_logging_and_config_redaction(db_session: AsyncSession, isolated_backup_dir: Path, caplog: pytest.LogCaptureFixture):
    """Verify secret credentials are never logged and are stripped from config archives."""
    with caplog.at_level(logging.INFO):
        service = BackupService(isolated_backup_dir)
        meta = await service.create_backup(db_session)

    # Verify log messages
    for record in caplog.records:
        msg = record.getMessage().lower()
        assert "password=" not in msg
        assert "secret_key=" not in msg
        assert "token=" not in msg
        assert "postgres://" not in msg
        assert "postgresql://" not in msg

    # Verify config archive redaction
    target_dir = isolated_backup_dir / meta["backup_id"]
    cfg_file = target_dir / "configuration.json.gz"
    import gzip
    with gzip.open(cfg_file, "rt", encoding="utf-8") as f:
        cfg_data = json.load(f)

    settings_dict = cfg_data.get("settings", {})
    for k, v in settings_dict.items():
        k_lower = k.lower()
        if any(sec in k_lower for sec in ("secret", "password", "token", "key", "uri", "url", "dsn")):
            assert v == "***REDACTED***", f"Field {k} was not redacted!"


@pytest.mark.asyncio
async def test_concurrent_backup_creation_and_idempotency(db_session: AsyncSession, isolated_backup_dir: Path):
    """Verify simultaneous backup creations execute cleanly without race conditions or filename collisions."""
    service = BackupService(isolated_backup_dir)

    # Execute 3 backups concurrently
    results = await asyncio.gather(
        service.create_backup(db_session),
        service.create_backup(db_session),
        service.create_backup(db_session),
    )

    backup_ids = [res["backup_id"] for res in results]
    assert len(set(backup_ids)) == 3, "Concurrent backups must generate distinct unique IDs"

    for b_id in backup_ids:
        assert (isolated_backup_dir / b_id / "metadata.json").exists()


def test_compressor_pluggability(tmp_path: Path):
    """Verify compression engine abstraction works without hardcoding."""
    compressor = get_compressor("gzip")
    test_file = tmp_path / "test.txt.gz"
    compressor.compress("Hello RealityTunnel", test_file)
    assert test_file.exists()
    assert test_file.stat().st_size > 0
