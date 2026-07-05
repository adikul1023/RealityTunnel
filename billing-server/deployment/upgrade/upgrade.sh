#!/usr/bin/env bash
# Automated Production Upgrade Script for RealityTunnel
set -eo pipefail

NEW_VERSION=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --version) NEW_VERSION="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$NEW_VERSION" ]; then
    echo "ERROR: --version is required (e.g., --version v1.1.0)"
    exit 1
fi

OLD_VERSION=${APP_VERSION:-1.0.0}
echo "── Starting RealityTunnel Upgrade from $OLD_VERSION to $NEW_VERSION ──"

echo "1. Creating pre-upgrade database backup..."
python3 -m app.recovery.backup --create --reason "pre_upgrade_${NEW_VERSION}" || echo "Warning: Backup command failed; ensure external DB snapshots exist."

export APP_VERSION="$NEW_VERSION"
export DOCKER_IMAGE="ghcr.io/adikul1023/realitytunnel:${NEW_VERSION}"

echo "2. Pulling target image $DOCKER_IMAGE..."
docker compose -f docker-compose.prod.yml pull billing-api || {
    echo "ERROR: Failed to pull image $DOCKER_IMAGE. Aborting upgrade."
    exit 1
}

echo "3. Recreating containers with new version..."
docker compose -f docker-compose.prod.yml up -d --remove-orphans billing-api

echo "4. Waiting for health check verification..."
retries=0
healthy=false
until [ $retries -ge 12 ]; do
    if curl -sf http://localhost:8080/health | grep -q '"status": "ok"'; then
        healthy=true
        break
    fi
    retries=$((retries+1))
    echo "Waiting for upgraded service... ($retries/12)"
    sleep 5
done

if [ "$healthy" = false ]; then
    echo "ERROR: Upgrade failed health check! Automatically initiating rollback to $OLD_VERSION..."
    ./deployment/rollback/rollback.sh --target-version "$OLD_VERSION"
    exit 1
fi

echo "5. Running smoke tests against upgraded container..."
TARGET_URL=http://localhost:8080 pytest tests/smoke/ -v || {
    echo "ERROR: Smoke tests failed! Automatically initiating rollback to $OLD_VERSION..."
    ./deployment/rollback/rollback.sh --target-version "$OLD_VERSION"
    exit 1
}

echo "── Upgrade to $NEW_VERSION Completed Successfully! ──"
