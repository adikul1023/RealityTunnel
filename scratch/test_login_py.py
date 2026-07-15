import os
import httpx
import win32crypt

def unprotect(filename):
    path = os.path.join(os.environ["LOCALAPPDATA"], "OverREALITY", "Secure", filename)
    with open(path, "rb") as f:
        data = f.read()
    decrypted = win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]
    return decrypted.decode("utf-8").strip().strip('"').strip()

account_id = unprotect("account_id.dat")
master_token = unprotect("master_token.dat")
device_guid = unprotect("device_guid.dat")

print("Account ID:", repr(account_id))
print("Device GUID:", repr(device_guid))

r_login = httpx.post("https://api.stealthy.co.in/api/auth/login", json={
    "account_id": account_id,
    "master_token": master_token,
    "device_guid": device_guid
}, timeout=10.0)

print("Login status:", r_login.status_code)
if r_login.status_code == 200:
    token = r_login.json()["access_token"]
    r_devs = httpx.get("https://api.stealthy.co.in/api/devices", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=10.0)
    print("GET /api/devices status:", r_devs.status_code)
    print("GET /api/devices body:", r_devs.json())

    r_hb = httpx.get("https://api.stealthy.co.in/api/devices/status", headers={
        "Authorization": f"Bearer {token}",
        "X-Device-Guid": device_guid
    }, timeout=10.0)
    print("GET /api/devices/status:", r_hb.status_code, r_hb.json())
else:
    print("Login response:", r_login.text)
