import httpx
import uuid

# Create a fresh account on prod
r_reg = httpx.post("https://api.stealthy.co.in/api/auth/register", json={
    "plan_id": "free"
})
reg_data = r_reg.json()
print("REGISTRATION STATUS:", r_reg.status_code)
print("REGISTERED CREDENTIALS:", reg_data)

account_id = reg_data["account_id"]
master_token = reg_data["master_token"]

# Attempt login with the Windows Client's exact device_guid
win_guid = "af652649-9ad0-4784-8b07-a0d4b44bd047"
r_login = httpx.post("https://api.stealthy.co.in/api/auth/login", json={
    "account_id": account_id,
    "master_token": master_token,
    "device_guid": win_guid
})
print("LOGIN WITH WINDOWS GUID:", r_login.status_code, r_login.text)

# Attempt login with a BRAND NEW web-style device_guid
web_guid = f"WEB-{uuid.uuid4()}"
r_login_web = httpx.post("https://api.stealthy.co.in/api/auth/login", json={
    "account_id": account_id,
    "master_token": master_token,
    "device_guid": web_guid
})
print("LOGIN WITH NEW WEB GUID:", r_login_web.status_code, r_login_web.text)
