# Troubleshooting & Recovery Guide

This guide describes common production issues, diagnostic techniques, and step-by-step remediation protocols for `realitytunnel-billing-server`.

## 1. Health Endpoint Returns `status: "error"` or `status: "degraded"`

### Symptom
Load balancers mark containers unhealthy, or `curl http://localhost:8080/health` reports `"status": "error"`.

### Diagnosis & Remediation
1. **Inspect Component Detail:**
   Check the `components` JSON dict in the `/health` response. Identify which subsystem (`postgresql`, `marzban`, `payment_gateway`) is reporting failure.
2. **PostgreSQL Connectivity Failure:**
   - Check if the database container is running: `docker compose -f docker-compose.prod.yml ps postgres`
   - Verify connection logs: `docker compose -f docker-compose.prod.yml logs --tail=50 billing-api | grep -i "database"`
   - Ensure network firewall permits traffic on port `5432` within `internal_net`.
3. **External Provider Degradation:**
   If `marzban` or `payment_gateway` is degraded while `postgresql` is `ok`, the overall status will report `degraded`. Under RealityTunnel fail-open philosophy, existing subscriptions will continue serving traffic without interruption.

---

## 2. Database Connection Pool Exhaustion (`QueuePool limit of size X overflow Y reached`)

### Symptom
Requests fail with HTTP 500 or 503, and logs contain `TimeoutError: QueuePool limit of size X overflow Y reached`.

### Remediation
1. **Check Active Pool Metrics:**
   Query `/api/metrics` and check `db_pool_active_connections` versus `db_pool_available_connections`.
2. **Scale Connection Limits:**
   If sustained traffic exceeds pool capacity, adjust pool parameters in `app/database.py` or scale database replicas.
3. **Inspect Long-Running Transactions:**
   Check PostgreSQL pg_stat_activity for stalled queries:
   ```sql
   SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC;
   ```

---

## 3. Container Startup Fails (`Permission denied` on `/app/backups` or `/app/brain`)

### Symptom
Container crashes on boot with `PermissionError: [Errno 13] Permission denied`.

### Remediation
1. In `docker-compose.prod.yml`, named volumes are mounted to `/app/backups` and `/app/brain`.
2. The Dockerfile creates user `billing` (UID 1001). Ensure host volume permissions or volume initialization match UID 1001.
3. Re-run container with `--build` flag to ensure ownership commands in the Dockerfile runtime stage take effect:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

---

## 4. Emergency Database Restoration

If database corruption occurs, restore from the last verified snapshot using the emergency recovery tool:
```bash
# 1. List available backup IDs
docker compose -f docker-compose.prod.yml exec billing-api python -m app.recovery.restore --list

# 2. Restore specific backup ID
docker compose -f docker-compose.prod.yml exec billing-api python -m app.recovery.restore --backup-id <BACKUP_ID> --confirm
```
