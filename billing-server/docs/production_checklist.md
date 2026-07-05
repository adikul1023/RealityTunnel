# RealityTunnel Production Hardening Checklist

Use this checklist to ensure complete compliance with RealityTunnel security, performance, and operational standards before opening production ingress to customer traffic.

## 1. Security & Identity Hardening

- [ ] **Non-Root Execution:** Verify Docker container executes under UID `1001` (`billing`) and never as `root`.
- [ ] **Read-Only Root Filesystem:** Ensure `read_only: true` is set in Compose/Kubernetes manifests, with explicit `tmpfs` mounted at `/tmp`.
- [ ] **Secret Management:** Confirm `SECRET_KEY`, `JWT_SECRET`, and database passwords are injected via secure secret managers (Docker Secrets / Vault / AWS Secrets Manager) and never committed to source control.
- [ ] **Zero-Secret Logging Verification:** Confirm all application log formatters strip and redact passwords, JWTs, master tokens, payment card details, and device ownership assertions.

## 2. High Availability & Database Engineering

- [ ] **Connection Pool Tuning:** Ensure SQLAlchemy connection pooling parameters (`pool_size`, `max_overflow`, `pool_timeout`) are tuned according to Phase 3.6 load testing results.
- [ ] **Automated Backup & Disaster Recovery:** Verify daily automated cron or background scheduled backups are running (`python -m app.recovery.backup --create`) and that WAL archiving is configured on PostgreSQL.
- [ ] **Idempotency & Concurrency:** Ensure payment webhooks and subscription provisioning endpoints enforce row-level locking (`SELECT FOR UPDATE`) and idempotency keys.

## 3. CI/CD & Artifact Integrity

- [ ] **SBOM Generation:** Verify CycloneDX and SPDX Software Bill of Materials are automatically attached to GitHub Releases.
- [ ] **Container Cryptographic Signing:** Confirm Docker images are signed using Cosign keyless OIDC signing in CI/CD pipelines.
- [ ] **Vulnerability Scanning:** Ensure zero critical/high CVEs exist in Python dependencies (`pip-audit`) and container filesystem (`Trivy`).

## 4. Observability & Telemetry

- [ ] **Prometheus Scraping:** Verify monitoring Prometheus server scrapes `/api/metrics` at 15-second intervals.
- [ ] **Health Endpoint Monitoring:** Configure load balancer health checks to poll `/health` every 10–15 seconds with a 5-second timeout.
