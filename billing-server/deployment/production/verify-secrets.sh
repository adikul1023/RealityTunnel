#!/usr/bin/env bash
# Pre-deployment Secrets Validator

set -euo pipefail

SECRETS_DIR="/opt/realitytunnel/secrets"
FAILED=0

function check_file() {
    local file_path="$1"
    local name="$2"
    
    if [[ ! -f "$file_path" ]]; then
        echo "✗ $name (Missing: $file_path)"
        FAILED=1
    elif [[ ! -s "$file_path" ]]; then
        echo "✗ $name (Empty: $file_path)"
        FAILED=1
    else
        echo "✓ $name"
    fi
}

echo "Verifying Production Secrets..."
echo "-------------------------------"

check_file "$SECRETS_DIR/jwt/ed25519_private.pem" "Customer JWT Private Key"
check_file "$SECRETS_DIR/jwt/ed25519_public.pem" "Customer JWT Public Key"
check_file "$SECRETS_DIR/jwt/admin/admin_ed25519_private.pem" "Admin JWT Private Key"
check_file "$SECRETS_DIR/jwt/admin/admin_ed25519_public.pem" "Admin JWT Public Key"
check_file "$SECRETS_DIR/backup/backup_public.pem" "Backup Public Key"
check_file "$SECRETS_DIR/env/.env.production" "Production Environment Variables (.env.production)"

if [[ $FAILED -ne 0 ]]; then
    echo "-------------------------------"
    echo "STOP: Missing required secrets. Deployment aborted."
    exit 1
fi

echo "-------------------------------"
echo "All required secrets are present."
exit 0
