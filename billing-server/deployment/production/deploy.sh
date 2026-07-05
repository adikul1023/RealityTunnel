#!/usr/bin/env bash
# Production Deployment Script for RealityTunnel Billing Server
set -eo pipefail

echo "── Starting RealityTunnel Production Deployment ──"

# 1. Verify environment variables
# NOTE (Finding H-1): JWT_SECRET was previously checked here but is dead configuration —
# it has no corresponding field in app/config.py::Settings and is never read by the
# application. Actual JWT signing uses Ed25519 PEM keypairs loaded from disk
# (dev_keys/ed25519_private.pem, dev_keys/admin/admin_ed25519_private.pem), which are
# validated at application startup by app.core.startup_validator.validate_startup_configuration()
# and will refuse to boot in production if missing or invalid. Only POSTGRES_PASSWORD is
# actually required by this script's own pre-flight guard.
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "ERROR: Required production environment variable POSTGRES_PASSWORD is not set!"
    exit 1
fi

export ENVIRONMENT=production
export DEBUG=false
export APP_VERSION=${APP_VERSION:-1.0.0}

echo "1. Creating pre-deployment database backup..."
python3 -m app.recovery.backup --create --reason "pre_deploy_${APP_VERSION}" || echo "Warning: Backup command failed or no local DB access; ensure external snapshots are active."

echo "2. Pulling latest production Docker images..."
docker compose -f docker-compose.prod.yml pull

echo "3. Starting containers in production mode..."
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "4. Waiting for health endpoint liveness..."
retries=0
max_retries=12
until curl -sf http://localhost:8080/health | grep -q '"status": "ok"'; do
    retries=$((retries+1))
    if [ $retries -ge $max_retries ]; then
        echo "ERROR: Health check timed out! Initiating automated container log dump..."
        docker compose -f docker-compose.prod.yml logs --tail=50 billing-api
        exit 1
    fi
    echo "Waiting for service... ($retries/$max_retries)"
    sleep 5
done

echo "5. Running automated smoke tests against production container..."
TARGET_URL=http://localhost:8080 pytest tests/smoke/ -v || {
    echo "ERROR: Smoke tests failed after deployment!"
    exit 1
}

echo "── Production Deployment Completed Successfully! ──"
