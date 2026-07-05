# RealityTunnel Production Deployment Checklist

Use this checklist before and after every production deployment of `realitytunnel-billing-server`.

## Pre-Deployment Verification

- [ ] **1. Secret Configuration & Environment**
  - [ ] `SECRET_KEY` is securely generated and distinct from development/staging keys.
  - [ ] `POSTGRES_PASSWORD` is set to a secure, randomly generated string.
  - [ ] Customer and Admin Ed25519 JWT signing keypairs (`dev_keys/ed25519_private.pem` /
        `ed25519_public.pem`, `dev_keys/admin/admin_ed25519_private.pem` / `admin_ed25519_public.pem`)
        are securely provisioned on disk before startup. There is no `JWT_SECRET` environment
        variable — JWT signing uses these Ed25519 PEM keypairs, and the application will refuse
        to boot in production if they are missing or invalid.
  - [ ] `ENVIRONMENT` is explicitly set to `production`.
  - [ ] `DEBUG` is explicitly set to `false`.
  - [ ] `LOG_LEVEL` is set to `INFO` or `WARNING`.

- [ ] **2. Infrastructure & Networking**
  - [ ] PostgreSQL 16+ server is accessible and configured with automated WAL archiving and daily snapshots.
  - [ ] TLS termination (Reverse Proxy / Load Balancer / Nginx / Cloudflare) is active and forcing HTTPS.
  - [ ] Firewall rules restrict port `5432` (PostgreSQL) exclusively to internal Docker/VPC networks.

- [ ] **3. Release Readiness**
  - [ ] CI/CD pipeline (`ci.yml`, `security.yml`, `docker.yml`) passed 100% green on `main`.
  - [ ] Docker image signed with Cosign is available in target registry.
  - [ ] Pre-deployment database backup created (`python -m app.recovery.backup --create --reason pre_deploy`).

---

## Deployment Steps

- [ ] **1. Execute Deployment Script**
  - [ ] Run `./deployment/production/deploy.sh` (Linux/macOS) or `.\deployment\production\deploy.ps1` (Windows).
  - [ ] Verify Docker Compose pulls the new tagged image and restarts containers cleanly.

---

## Post-Deployment Verification

- [ ] **1. Health Check & Smoke Tests**
  - [ ] Execute `curl -sf https://api.yourdomain.com/health | jq .` and verify `status: "ok"` and `version: "1.0.0"`.
  - [ ] Execute automated smoke test suite against live production endpoint:
        `TARGET_URL=https://api.yourdomain.com pytest tests/smoke/ -v`

- [ ] **2. Observability & Monitoring**
  - [ ] Verify Prometheus metrics endpoint `/api/metrics` is scraping correctly.
  - [ ] Check container logs (`docker compose -f docker-compose.prod.yml logs --tail=100 -f billing-api`) for zero unhandled exceptions or stack traces.
  - [ ] Verify connection pool metrics (`db_pool_active_connections`, `db_pool_available_connections`) are healthy.

---

## Rollback Protocol (If Post-Deployment Fails)

- [ ] Immediately execute `./deployment/rollback/rollback.sh --target-version <PREVIOUS_TAG>` or Windows equivalent.
- [ ] Follow instructions in `deployment/rollback/ROLLBACK_GUIDE.md`.
