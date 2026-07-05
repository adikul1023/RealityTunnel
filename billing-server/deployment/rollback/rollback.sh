#!/usr/bin/env bash
# Automated Production Rollback Script for RealityTunnel
set -eo pipefail

TARGET_VERSION=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --target-version) TARGET_VERSION="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$TARGET_VERSION" ]; then
    echo "ERROR: --target-version is required (e.g., --target-version v0.9.0)"
    exit 1
fi

echo "── Initiating Emergency Rollback to $TARGET_VERSION ──"

export APP_VERSION="$TARGET_VERSION"
export DOCKER_IMAGE="ghcr.io/adikul1023/realitytunnel:${TARGET_VERSION}"

echo "1. Pulling rollback image $DOCKER_IMAGE..."
docker compose -f docker-compose.prod.yml pull billing-api

echo "2. Restarting service with previous version..."
docker compose -f docker-compose.prod.yml up -d --remove-orphans billing-api

echo "3. Verifying health endpoint..."
retries=0
until curl -sf http://localhost:8080/health | grep -q '"status": "ok"'; do
    retries=$((retries+1))
    if [ $retries -ge 10 ]; then
        echo "ERROR: Rollback health check failed!"
        docker compose -f docker-compose.prod.yml logs --tail=50 billing-api
        exit 1
    fi
    sleep 3
done

echo "4. Running smoke tests against rolled back instance..."
TARGET_URL=http://localhost:8080 pytest tests/smoke/ -v || {
    echo "ERROR: Smoke tests failed after rollback!"
    exit 1
}

echo "── Rollback to $TARGET_VERSION Completed Successfully! ──"
