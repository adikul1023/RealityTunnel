# RealityTunnel Production Rollback Guide

In the event of a severe production regression, failing smoke test, or unhandled exception surge after deploying a new release, follow this emergency rollback procedure.

## 1. Automated Rollback (Recommended)

Execute the automated rollback script, passing the target stable release tag:

### Linux / macOS
```bash
./deployment/rollback/rollback.sh --target-version v1.0.0
```

### Windows (PowerShell)
```powershell
.\deployment\rollback\rollback.ps1 -TargetVersion "v1.0.0"
```

## 2. Manual Rollback Procedure

If automated rollback is unavailable, perform the following steps:

1. **Set Target Docker Image Version:**
   In your environment or `.env` file, change `DOCKER_IMAGE` or `APP_VERSION` back to the last known stable tag:
   ```bash
   export DOCKER_IMAGE="ghcr.io/adikul1023/realitytunnel:v0.9.0"
   export APP_VERSION="0.9.0"
   ```

2. **Restart Docker Compose Service:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d --remove-orphans
   ```

3. **Verify Health & Smoke Tests:**
   ```bash
   curl -s http://localhost:8080/health | jq .
   TARGET_URL=http://localhost:8080 pytest tests/smoke/ -v
   ```

## 3. Database State Rollback (If Migrations Weren't Backward-Compatible)

If the deployment altered database schemas in an incompatible way:
1. Stop API traffic: `docker compose -f docker-compose.prod.yml stop billing-api`
2. Restore from pre-deployment snapshot using Phase 3.4 recovery tooling:
   ```bash
   python -m app.recovery.restore --backup-id <PRE_DEPLOY_BACKUP_ID> --confirm
   ```
3. Start API service: `docker compose -f docker-compose.prod.yml start billing-api`
