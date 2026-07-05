# RealityTunnel Production Deployment Guide

This document provides step-by-step instructions for deploying `realitytunnel-billing-server` in a production environment using Docker Compose and automated release scripts.

## 1. System Requirements

- **Operating System:** Ubuntu 22.04 LTS / Debian 12 / Windows Server 2022 / RHEL 9
- **Container Runtime:** Docker Engine 24.0+ and Docker Compose v2.20+
- **Database:** PostgreSQL 16+ (Managed service like RDS/Cloud SQL or dedicated container)
- **Hardware Minimums:** 2 CPU Cores, 2 GB RAM, 20 GB NVMe Storage

## 2. Preparing Environment & Secrets

Never use development defaults in production. Prepare a secure `.env` file in your production directory:

```ini
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
APP_VERSION=1.0.0
DOCKER_IMAGE=ghcr.io/adikul1023/realitytunnel:v1.0.0

# Database Configuration
POSTGRES_HOST=postgres.prod.internal
POSTGRES_PORT=5432
POSTGRES_DB=billing_prod
POSTGRES_USER=billing_master
POSTGRES_PASSWORD=<SECURE_RANDOM_PASSWORD_HERE>

# Cryptographic Keys (Must be 32+ bytes random hex/base64)
SECRET_KEY=<GENERATE_WITH: openssl rand -hex 32>
JWT_SECRET=<GENERATE_WITH: openssl rand -hex 32>
```

## 3. Initial Deployment Using Automated Scripts

We provide automated deployment scripts that execute pre-flight database snapshots, pull verified container artifacts, restart services cleanly, wait for health liveness, and execute automated smoke tests.

### Linux / macOS Deployment
```bash
chmod +x deployment/production/deploy.sh
./deployment/production/deploy.sh
```

### Windows Deployment (PowerShell)
```powershell
.\deployment\production\deploy.ps1
```

## 4. Verification & Liveness Checks

Once deployed, check container status and execute manual health inspection:
```bash
# Check running container health
docker compose -f docker-compose.prod.yml ps

# Inspect detailed health response
curl -s http://localhost:8080/health | jq .
```

A healthy response will output:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "git_commit": "a1b2c3d...",
  "build_date": "2026-07-05...",
  "docker_image": "ghcr.io/adikul1023/realitytunnel:v1.0.0",
  "components": {
    "postgresql": { "status": "ok", "detail": "Connected" }
  }
}
```
