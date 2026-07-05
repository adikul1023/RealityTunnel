# RealityTunnel Production Upgrade Guide

Follow these guidelines to upgrade a running production instance of `realitytunnel-billing-server` with zero or minimal downtime.

## 1. Upgrade Philosophy

- **Zero-Secret Caching Rule:** Caching layers never hold sensitive tokens or device ownership, so restarting nodes will not invalidate security assertions.
- **Fail-Open & Database Safety:** All production upgrades MUST be preceded by an automated snapshot/backup.
- **Backward-Compatible Schemas:** When adding database columns or tables, always deploy code that reads/writes both old and new schemas before dropping deprecated structures.

## 2. Automated Upgrade Procedure

Run the automated upgrade script, passing the target release version tag:

### Linux / macOS
```bash
./deployment/upgrade/upgrade.sh --version v1.1.0
```

### Windows (PowerShell)
```powershell
.\deployment\upgrade\upgrade.ps1 -Version "v1.1.0"
```

## 3. What the Upgrade Script Does

1. **Pre-Upgrade Backup:** Triggers Phase 3.4 recovery tooling (`app.recovery.backup`) to snapshot PostgreSQL and configuration metadata.
2. **Pull New Artifacts:** Pulls the signed Docker image for the target version from GitHub Container Registry (`ghcr.io`).
3. **Rolling Container Upgrade:** Executes `docker compose up -d` to recreate containers cleanly with the new image.
4. **Health & Smoke Test Verification:** Polls `/health` for HTTP 200 and version matching, then executes `pytest tests/smoke/ -v`.
5. **Automated Rollback Trigger:** If health checks or smoke tests fail during upgrade, the script automatically reverts containers to the previous version.
