"""
setup_regression_account.py
============================
One-time script to create the permanent ST-REGRESSION account.

This script:
  1. Registers a new account via the public API
  2. Registers the fixed device GUID
  3. SAVES credentials to tests/regression/.env.regression
  4. Then activates the account directly via Postgres (no interactive admin password needed)

Usage:
    python scratch/setup_regression_account.py

Re-running is safe — it detects existing credentials and skips re-registration.
"""

import httpx
import sys
import os
import subprocess

BASE_URL             = "http://127.0.0.1:8080"
REGRESSION_DEVICE_GUID = "st-regression-device-0001-000000000000"
ORACLE_SSH_KEY       = r"d:\My projects\VPN\AWSKEY\ssh-key-2026-03-01.key"
ORACLE_HOST          = "ubuntu@144.24.153.180"
POSTGRES_CONTAINER   = "09a78c2b9503db66b6ac31aed64f650faba94d67-postgres-1"

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE  = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "tests", "regression", ".env.regression"))


def run_sql(sql: str) -> str:
    """Execute SQL on the local Postgres container."""
    sql_file = "/tmp/_regression_setup.sql"
    local_tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "_regression_setup.sql")
    with open(local_tmp, "w") as f:
        f.write(sql)
    subprocess.run(
        ["docker", "cp", local_tmp, f"billing-server-postgres-1:{sql_file}"],
        check=True, capture_output=True
    )
    result = subprocess.run(
        ["docker", "exec", "billing-server-postgres-1", "psql", "-U", "billing", "-d", "billing", "-f", sql_file],
        capture_output=True, text=True
    )
    return result.stdout + result.stderr


def save_credentials(account_id: str, master_token: str):
    os.makedirs(os.path.dirname(CREDS_FILE), exist_ok=True)
    with open(CREDS_FILE, "w") as f:
        f.write("# ST-REGRESSION account credentials — DO NOT COMMIT\n")
        f.write(f"REGRESSION_ACCOUNT_ID={account_id}\n")
        f.write(f"REGRESSION_MASTER_TOKEN={master_token}\n")
        f.write(f"REGRESSION_DEVICE_GUID={REGRESSION_DEVICE_GUID}\n")
    print(f"[+] Credentials saved to: {CREDS_FILE}")


def load_credentials():
    if not os.path.exists(CREDS_FILE):
        return None
    creds = {}
    with open(CREDS_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()
    return creds


def activate_account_via_db(account_id: str):
    print(f"[*] Activating {account_id} via Postgres...")
    sql = f"""
UPDATE accounts
SET status = 'ACTIVE',
    subscription_expires_at = NOW() + INTERVAL '3650 days',
    updated_at = NOW()
WHERE account_id = '{account_id}' AND status != 'ACTIVE';

SELECT account_id, status, subscription_expires_at
FROM accounts WHERE account_id = '{account_id}';
"""
    out = run_sql(sql)
    print(out.strip())
    if "ACTIVE" in out:
        print(f"[+] Account {account_id} is ACTIVE with subscription until ~2036.")
    else:
        print(f"[!] Warning: could not confirm activation. Check output above.")


def setup():
    # ── Step 1: Check for existing credentials ─────────────────────────────
    existing = load_credentials()
    if existing:
        print(f"[!] Credentials already exist for {existing.get('REGRESSION_ACCOUNT_ID')}.")
        choice = input("    Force re-create? [y/N]: ").strip().lower()
        if choice != "y":
            account_id = existing["REGRESSION_ACCOUNT_ID"]
            print(f"[*] Using existing account. Re-activating {account_id} in case subscription expired...")
            activate_account_via_db(account_id)
            print("[+] Done. Existing regression account is ready.")
            return

    # ── Step 2: Register account ───────────────────────────────────────────
    print("[*] Registering new ST-REGRESSION account...")
    r_reg = httpx.post(f"{BASE_URL}/api/auth/register", json={"plan_id": "free"}, timeout=10.0)
    if r_reg.status_code != 201:
        print(f"[-] Registration failed: {r_reg.text}")
        sys.exit(1)

    reg = r_reg.json()
    account_id   = reg["account_id"]
    master_token = reg["master_token"]
    print(f"[+] Registered: {account_id}")

    # ── Step 3: SAVE credentials immediately (before anything can go wrong) ─
    save_credentials(account_id, master_token)

    # ── Step 4: Activate via DB FIRST (accounts start INACTIVE) ──────────
    activate_account_via_db(account_id)

    # ── Step 5: Register device (requires ACTIVE account) ─────────────────
    print(f"[*] Registering device '{REGRESSION_DEVICE_GUID}'...")
    r_login = httpx.post(f"{BASE_URL}/api/auth/login", json={
        "account_id": account_id,
        "master_token": master_token,
        "device_guid": REGRESSION_DEVICE_GUID,
    }, timeout=10.0)
    if r_login.status_code != 200:
        print(f"[-] Login/device registration failed: {r_login.text}")
        sys.exit(1)
    access_token = r_login.json()["access_token"]
    print(f"[+] Device registered.")

    # ── Step 6: Verify /api/client/config ─────────────────────────────────
    print(f"[*] Verifying /api/client/config...")
    r_config = httpx.get(f"{BASE_URL}/api/client/config", headers={
        "Authorization": f"Bearer {access_token}",
        "X-Device-ID": REGRESSION_DEVICE_GUID,
    }, timeout=10.0)

    if r_config.status_code != 200:
        print(f"[-] Config fetch failed: {r_config.text}")
        print(f"    Note: The account may need a few seconds after activation.")
        sys.exit(1)

    cfg = r_config.json()
    vp = cfg.get("vpn_profile", cfg)
    print(f"[+] Config OK: server={vp.get('server_host')} sni={vp.get('sni')} port={vp.get('server_port')}")

    print(f"\n{'='*60}")
    print(f"  ST-REGRESSION account is ready.")
    print(f"  Account ID  : {account_id}")
    print(f"  Device GUID : {REGRESSION_DEVICE_GUID}")
    print(f"  Creds file  : {CREDS_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    setup()
