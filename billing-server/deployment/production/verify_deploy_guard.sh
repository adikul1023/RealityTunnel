#!/usr/bin/env bash
# Manual verification script for Finding C-5 (deploy.sh secret guard).
# Proves the guard exits non-zero when POSTGRES_PASSWORD is unset and proceeds when set.
# Usage: ./deployment/production/verify_deploy_guard.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SH="${SCRIPT_DIR}/deploy.sh"

extract_guard() {
    # Reproduce only the guard stanza from deploy.sh (lines starting at the if [ -z check).
    sed -n '/^if \[ -z "\$POSTGRES_PASSWORD" \]; then/,/^fi$/p' "$DEPLOY_SH"
}

run_guard() {
    local postgres_password="${1-}"
    (
        unset POSTGRES_PASSWORD JWT_SECRET MASTER_TOKEN_HASH API_KEY
        export POSTGRES_PASSWORD="$postgres_password"
        eval "$(extract_guard)"
    )
}

echo "== C-5 guard verification: POSTGRES_PASSWORD unset =="
if run_guard ""; then
    echo "FAIL: guard should have exited non-zero when POSTGRES_PASSWORD is unset"
    exit 1
fi
echo "PASS: guard blocked deployment when POSTGRES_PASSWORD is unset"

echo "== C-5 guard verification: POSTGRES_PASSWORD set (JWT_SECRET still unset) =="
if ! run_guard "manual-verification-password"; then
    echo "FAIL: guard should not block when only POSTGRES_PASSWORD is set"
    exit 1
fi
echo "PASS: guard allowed continuation when POSTGRES_PASSWORD is set"

echo "All deploy guard checks passed."
