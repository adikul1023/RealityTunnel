import httpx
import subprocess
import json
import datetime
import uuid

SSH_KEY = r"d:\My projects\VPN\AWSKEY\ssh-key-2026-03-01.key"
SSH_HOST = "ubuntu@144.24.153.180"
CONTAINER = "09a78c2b9503db66b6ac31aed64f650faba94d67-postgres-1"
BASE_URL = "https://api.stealthy.co.in"

def run_prod_sql(sql_query):
    cmd = [
        "ssh", "-o", "ConnectTimeout=15", "-i", SSH_KEY, SSH_HOST,
        f"sudo docker exec -i {CONTAINER} psql -U billing -d billing"
    ]
    res = subprocess.run(cmd, input=sql_query, capture_output=True, text=True)
    return res.stdout.strip()

print("=== SYNCHRONIZED END-TO-END TRACE ON PRODUCTION ===")
now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
print(f"Time (UTC): {now_utc}")

# Check who owns the Windows client's actual GUID across ALL accounts in prod DB
guid_to_check = "af652649-9ad0-4784-8b07-a0d4b44bd047"
print(f"\n--- Pre-check: Ownership of Windows client GUID {guid_to_check} across all accounts ---")
sql_owner = f"SELECT d.device_guid, a.account_id, d.is_active, d.first_seen_at, d.last_seen_at FROM devices d JOIN accounts a ON d.account_id = a.id WHERE d.device_guid = '{guid_to_check}';"
owner_output = run_prod_sql(sql_owner)
print("SQL Output:")
print(owner_output if owner_output else "[No row found]")

with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
    print("\n--- Step 0: Register Synchronized Test Account ---")
    r_reg = client.post("/api/auth/register", json={"plan_id": "free"})
    assert r_reg.status_code == 201, f"Reg failed: {r_reg.text}"
    reg_data = r_reg.json()
    acc_id = reg_data["account_id"]
    master_token = reg_data["master_token"]
    test_guid = f"af652649-9ad0-4784-8b07-{uuid.uuid4().hex[:12]}"

    print(f"Test Account ID: {acc_id}")
    print(f"Test Device GUID: {test_guid}")

    print("\n--- Step 1: Login Request ---")
    login_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(f"Login timestamp: {login_ts}")
    r_login = client.post("/api/auth/login", json={
        "account_id": acc_id,
        "master_token": master_token,
        "device_guid": test_guid
    })
    print(f"HTTP Status: {r_login.status_code}")
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"
    access_token = r_login.json()["access_token"]

    print("\n--- Step 2: Production Database State immediately after login ---")
    sql_acc = f"SELECT a.account_id, d.device_guid, d.is_active, d.first_seen_at, d.last_seen_at FROM devices d JOIN accounts a ON d.account_id = a.id WHERE a.account_id = '{acc_id}';"
    db_rows = run_prod_sql(sql_acc)
    print("Actual rows in prod DB:")
    print(db_rows)

    print("\n--- Step 3: Raw GET /api/devices JSON response immediately afterwards ---")
    r_devs = client.get("/api/devices", headers={"Authorization": f"Bearer {access_token}"})
    print(f"HTTP Status: {r_devs.status_code}")
    print(f"Response length: {len(r_devs.text)} bytes")
    print("Raw JSON payload:")
    print(r_devs.text)

    print("\n--- Step 4: Cross-account ownership verification ---")
    sql_check_one = f"SELECT a.account_id FROM devices d JOIN accounts a ON d.account_id = a.id WHERE d.device_guid = '{test_guid}';"
    check_one_res = run_prod_sql(sql_check_one)
    print(f"SELECT account_id FROM devices WHERE device_guid = '{test_guid}':")
    print(check_one_res)
