"""
test_admin_recovery.py — Integration tests for administrative recovery API endpoints (Phase 3.4).
"""
import shutil
from pathlib import Path
import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.fixture(autouse=True)
def isolated_backup_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure every test runs against a clean temporary backup directory."""
    b_dir = tmp_path / "test_admin_recovery_backups"
    b_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "backup_directory", str(b_dir))
    yield b_dir
    if b_dir.exists():
        shutil.rmtree(b_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_admin_recovery_lifecycle_endpoints(
    async_client: AsyncClient,
    admin_auth_headers_factory,
):
    """Verify admin endpoints for backup creation, listing, preview, verification, and pruning."""
    super_admin_auth_headers, _ = await admin_auth_headers_factory(is_super_admin=True, username="sa_rec")
    admin_auth_headers, _ = await admin_auth_headers_factory(is_super_admin=False, username="reg_rec")

    # 1. Create backup via super admin
    res = await async_client.post("/api/admin/recovery/backups", headers=super_admin_auth_headers)
    assert res.status_code == 201, res.text
    meta = res.json()
    backup_id = meta["backup_id"]
    assert backup_id.startswith("backup_")

    # 2. List backups via admin
    res_list = await async_client.get("/api/admin/recovery/backups", headers=admin_auth_headers)
    assert res_list.status_code == 200
    backups = res_list.json()
    assert len(backups) == 1
    assert backups[0]["backup_id"] == backup_id

    # 3. Get restore preview
    res_prev = await async_client.get(f"/api/admin/recovery/backups/{backup_id}/preview", headers=admin_auth_headers)
    assert res_prev.status_code == 200
    prev = res_prev.json()
    assert prev["backup_id"] == backup_id
    assert prev["can_restore"] is True

    # 4. Verify integrity via super admin
    res_ver = await async_client.post(f"/api/admin/recovery/backups/{backup_id}/verify", headers=super_admin_auth_headers)
    assert res_ver.status_code == 200
    ver = res_ver.json()
    assert ver["status"] == "ok"
    assert ver["checksums_valid"] is True

    # 5. Prune backups via super admin
    res_prune = await async_client.post("/api/admin/recovery/prune", headers=super_admin_auth_headers)
    assert res_prune.status_code == 200
    assert res_prune.json()["status"] == "ok"
