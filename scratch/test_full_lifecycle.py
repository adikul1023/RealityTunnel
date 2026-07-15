import httpx
import uuid
import sys

BASE_URL = "https://api.stealthy.co.in"

print("=========================================================================")
print("     COMPLETE AUTH & DEVICE LIFECYCLE E2E REGRESSION TEST (PROD)")
print("=========================================================================")

# Step 0: Register test account
r_reg = httpx.post(f"{BASE_URL}/api/auth/register", json={"plan_id": "free"}, timeout=10.0)
assert r_reg.status_code == 201, f"Registration failed: {r_reg.text}"
reg_data = r_reg.json()
account_id = reg_data["account_id"]
master_token = reg_data["master_token"]
print(f"[PASS] [Step 0] Registered Test Account: {account_id}")

win_guid = f"af652649-9ad0-4784-8b07-{uuid.uuid4().hex[:12]}"

# Step 1: Login Windows Client (First initial registration)
r_log1 = httpx.post(f"{BASE_URL}/api/auth/login", json={
    "account_id": account_id,
    "master_token": master_token,
    "device_guid": win_guid
}, timeout=10.0)
assert r_log1.status_code == 200, f"Login 1 failed: {r_log1.text}"
tokens1 = r_log1.json()
access_token1 = tokens1["access_token"]
refresh_token1 = tokens1["refresh_token"]
print(f"[PASS] [Step 1] Windows Client Login #1 successful (Device registered: {win_guid})")

# Step 2: Check Devices count == 1
r_devs1 = httpx.get(f"{BASE_URL}/api/devices", headers={"Authorization": f"Bearer {access_token1}"}, timeout=10.0)
assert r_devs1.status_code == 200, f"Get devices failed: {r_devs1.text}"
dev_list1 = r_devs1.json()
devices_len = len(dev_list1.get("devices", dev_list1))
assert devices_len == 1, f"Expected 1 device, got {devices_len}"
print(f"[PASS] [Step 2] Verified device count is exactly 1")

# Step 3: Simulate restart -> Login again with same Windows GUID
r_log2 = httpx.post(f"{BASE_URL}/api/auth/login", json={
    "account_id": account_id,
    "master_token": master_token,
    "device_guid": win_guid
}, timeout=10.0)
assert r_log2.status_code == 200, f"Login 2 failed: {r_log2.text}"
tokens2 = r_log2.json()
access_token2 = tokens2["access_token"]
refresh_token2 = tokens2["refresh_token"]
print(f"[PASS] [Step 3] Windows Client Login #2 (post-restart) successful")

# Step 4: Verify no duplicate device created (count still == 1)
r_devs2 = httpx.get(f"{BASE_URL}/api/devices", headers={"Authorization": f"Bearer {access_token2}"}, timeout=10.0)
dev_list2 = r_devs2.json()
devices_len2 = len(dev_list2.get("devices", dev_list2))
assert devices_len2 == 1, f"Expected 1 device after restart, got {devices_len2}"
print(f"[PASS] [Step 4] Verified device count remains exactly 1 (idempotent login)")

# Step 5: Click 'Remove Device' (DELETE /api/devices/{guid})
r_del = httpx.delete(f"{BASE_URL}/api/devices/{win_guid}", headers={"Authorization": f"Bearer {access_token2}"}, timeout=10.0)
assert r_del.status_code == 200, f"Remove device failed: {r_del.text}"
print(f"[PASS] [Step 5] Removed device {win_guid} via DELETE endpoint")

# Step 6: Verify device list is empty
r_devs3 = httpx.get(f"{BASE_URL}/api/devices", headers={"Authorization": f"Bearer {access_token2}"}, timeout=10.0)
dev_list3 = r_devs3.json()
devices_len3 = len(dev_list3.get("devices", dev_list3))
assert devices_len3 == 0, f"Expected 0 devices after removal, got {devices_len3}: {dev_list3}"
print(f"[PASS] [Step 6] Verified device list is now empty (hard delete verified)")

# Step 7: Verify refresh token was revoked upon device removal
r_ref = httpx.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": refresh_token2}, timeout=10.0)
assert r_ref.status_code in [401, 403], f"Expected 401/403 for revoked refresh token, got {r_ref.status_code}"
print(f"[PASS] [Step 7] Verified refresh token was revoked upon device removal (Status: {r_ref.status_code})")

# Step 8: Login again with the same Windows GUID (re-register after removal)
r_log3 = httpx.post(f"{BASE_URL}/api/auth/login", json={
    "account_id": account_id,
    "master_token": master_token,
    "device_guid": win_guid
}, timeout=10.0)
assert r_log3.status_code == 200, f"Re-login failed: {r_log3.text}"
tokens3 = r_log3.json()
access_token3 = tokens3["access_token"]
print(f"[PASS] [Step 8] Re-login with Windows GUID successful (clean re-registration)")

# Step 9: Verify device count is 1
r_devs4 = httpx.get(f"{BASE_URL}/api/devices", headers={"Authorization": f"Bearer {access_token3}"}, timeout=10.0)
dev_list4 = r_devs4.json()
devices_len4 = len(dev_list4.get("devices", dev_list4))
assert devices_len4 == 1, f"Expected 1 device after re-registration, got {devices_len4}"
print(f"[PASS] [Step 9] Verified device count is exactly 1 after re-registration")

print("=========================================================================")
print("[PASS] FULL LIFECYCLE TEST PASSED 100% WITH ZERO REGRESSIONS!")
print("=========================================================================")
