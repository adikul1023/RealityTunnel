import httpx
import uuid

# 1. Register on Prod
account_id = f"test_prod_{uuid.uuid4().hex[:8]}"
r_prod = httpx.post("https://api.stealthy.co.in/api/auth/register", json={
    "account_id": account_id,
    "master_token": "hash123",
    "plan_type": "free"
})
print(f"Prod Register {account_id}:", r_prod.status_code)

# 2. Register on Local
account_id_loc = f"test_loc_{uuid.uuid4().hex[:8]}"
r_loc = httpx.post("http://localhost:8088/api/auth/register", json={
    "account_id": account_id_loc,
    "master_token": "hash123",
    "plan_type": "free"
})
print(f"Local Register {account_id_loc}:", r_loc.status_code)
