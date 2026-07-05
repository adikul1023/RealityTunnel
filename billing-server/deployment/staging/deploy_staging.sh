#!/usr/bin/env bash
# Staging Deployment Script for RealityTunnel Billing Server
set -eo pipefail

echo "── Starting RealityTunnel Staging Deployment ──"

export ENVIRONMENT=staging
export DEBUG=true
export APP_VERSION=${APP_VERSION:-1.0.0-rc.1}
export POSTGRES_DB=${POSTGRES_DB:-billing_staging}

echo "1. Pulling staging Docker images..."
docker compose -f docker-compose.prod.yml pull || true

echo "2. Building and starting containers in staging mode..."
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans

echo "3. Waiting for health endpoint liveness..."
retries=0
max_retries=10
until curl -sf http://localhost:8080/health | grep -q "version"; do
    retries=$((retries+1))
    if [ $retries -ge $max_retries ]; then
        echo "ERROR: Staging health check timed out!"
        docker compose -f docker-compose.prod.yml logs --tail=50 billing-api
        exit 1
    fi
    sleep 3
done

echo "4. Running full regression and smoke tests against staging..."
TARGET_URL=http://localhost:8080 pytest tests/smoke/ -v

echo "── Staging Deployment & Verification Completed! ──"
