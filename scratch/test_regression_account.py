import httpx, json

BASE = "https://api.stealthy.co.in"
creds = {}
with open(r"d:\My projects\VPN\OverREALITY\tests\regression\.env.regression") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            creds[k] = v

r = httpx.post(f"{BASE}/api/auth/login", json={
    "account_id": creds["REGRESSION_ACCOUNT_ID"],
    "master_token": creds["REGRESSION_MASTER_TOKEN"],
    "device_guid": creds["REGRESSION_DEVICE_GUID"],
}, timeout=10)
print("Login:", r.status_code)
if r.status_code != 200:
    print(r.text)
    raise SystemExit(1)

token = r.json()["access_token"]
r2 = httpx.get(f"{BASE}/api/client/config", headers={
    "Authorization": f"Bearer {token}",
    "X-Device-ID": creds["REGRESSION_DEVICE_GUID"],
}, timeout=10)
print("Config:", r2.status_code)
print(json.dumps(r2.json(), indent=2))
