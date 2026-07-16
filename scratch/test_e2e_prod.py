import asyncio
import httpx
import json
import os
import uuid
import time
import subprocess
import shutil

ADMIN_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDAiLCJ1c2VybmFtZSI6InN1cGVyYWRtaW4iLCJyb2xlIjoic3VwZXJfYWRtaW4iLCJpc3MiOiJSZWFsaXR5VHVubmVsIEFkbWluIiwiYXVkIjoiUmVhbGl0eVR1bm5lbCBBZG1pbiBQYW5lbCIsImlhdCI6MTc4NDExOTQzMCwibmJmIjoxNzg0MTE5NDMwLCJleHAiOjE3ODQyMDU4MzB9.3hPqXSR-chlrSQEVgHCOeGbSjaPtVp2j_p-R8cZHq_vPNYYkV9Q56ri1i0gNfvq5VIYKh2jNU8Gfxf5ZCS7sDA"

async def main():
    # We will use production URL
    BASE_URL = "https://api.stealthy.co.in/api"
    
    unique_id = str(uuid.uuid4())[:8]
    username = f"betatest_{unique_id}"
    password = "TestPassword123!"
    
    async with httpx.AsyncClient() as client:
        print("1. Registering account...")
        reg_res = await client.post(f"{BASE_URL}/auth/register", json={
            "username": username,
            "password": password,
            "client_id": "windows_beta",
            "device_guid": unique_id
        })
        reg_res.raise_for_status()
        print("Register successful:", reg_res.json())
        
        master_token = reg_res.json()["master_token"]
        
        print("\n2. Logging in...")
        login_res = await client.post(f"{BASE_URL}/auth/login", json={
            "account_id": reg_res.json()["account_id"],
            "master_token": master_token,
            "client_id": "windows_beta",
            "device_guid": unique_id
        })
        login_res.raise_for_status()
        tokens = login_res.json()
        access_token = tokens["access_token"]
        print("Login successful. Got access token.")
        
        print("\n3. Verifying initial /client/me (Should be empty subscription)...")
        me_res = await client.get(f"{BASE_URL}/client/me", headers={"Authorization": f"Bearer {access_token}"})
        me_res.raise_for_status()
        me_data = me_res.json()
        account_id_str = me_data["account_id"]
        print(f"Me data: {me_data}")
        print(f"Account ID is: {account_id_str}")
        assert me_data.get("plan") == "free", "Should be free plan initially"
        
        # Use valid production admin token
        ADMIN_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDAiLCJ1c2VybmFtZSI6InN1cGVyYWRtaW4iLCJyb2xlIjoic3VwZXJfYWRtaW4iLCJpc3MiOiJSZWFsaXR5VHVubmVsIEFkbWluIiwiYXVkIjoiUmVhbGl0eVR1bm5lbCBBZG1pbiBQYW5lbCIsImlhdCI6MTc4NDEyMDM2NywibmJmIjoxNzg0MTIwMzY3LCJleHAiOjE3ODQyMDY3NjcsImp0aSI6IjZlN2VmYWMxLWQwMzAtNDc0YS04MmI2LTA3OGQ4NjljY2FlZSJ9.Nf0oY764ewyoSEvmG3mh4X3QhKKLk4Q04BMGOKFG3A_s-C-PnnwjFgH2ZB6B35PFtDqSC_y0MWmOIU71ULK5Dg"
        
        print("\n4. Admin granting subscription (Standard Plan, 30 days)...")
        grant_res = await client.post(
            f"{BASE_URL}/admin/accounts/{account_id_str}/grant-subscription",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            json={
                "plan_id": "standard",
                "duration_days": 30,
                "notes": "E2E Beta Flow Test"
            }
        )
        print("Grant Response:", grant_res.status_code, grant_res.text)
        grant_res.raise_for_status()
        grant_data = grant_res.json()
        print(f"Grant successful: {grant_data}")
        
        print("\n5. Verifying /client/me reflects active subscription...")
        me_res2 = await client.get(f"{BASE_URL}/client/me", headers={"Authorization": f"Bearer {access_token}"})
        me_res2.raise_for_status()
        me_data2 = me_res2.json()
        print(f"Me data after grant: {me_data2}")
        assert me_data2.get("plan") == "standard", "Plan should be standard"
        
        print("\n6. Fetching /client/config...")
        config_res = await client.get(f"{BASE_URL}/client/config", headers={"Authorization": f"Bearer {access_token}", "X-Device-ID": unique_id})
        if config_res.status_code >= 400:
            print(f"Error getting config: {config_res.text}")
        config_res.raise_for_status()
        config_data = config_res.json()
        
        # Save config
        config_path = "test_e2e_config.json"
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)
        print(f"Config downloaded and saved to {config_path}")
        
        print("\n7. Simulating Windows Client connection (sing-box)...")
        
        # Check if sing-box is available
        singbox_path = shutil.which("sing-box")
        if not singbox_path:
            # Let's try downloading singbox binary or just assume it's there
            # Or use sing-box.exe if on Windows
            singbox_path = "sing-box"
            
        print("Starting sing-box...")
        # Start sing-box in the background
        process = subprocess.Popen([singbox_path, "run", "-c", config_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            print("Waiting for VPN to connect (5 seconds)...")
            time.sleep(5)
            
            print("8. Testing traffic routing through the VPN (using curl + socks5)")
            inbound_port = None
            for inbound in config_data.get("inbounds", []):
                if inbound.get("type") in ["mixed", "socks", "http"]:
                    inbound_port = inbound.get("listen_port")
                    break
            
            if inbound_port:
                print(f"Found inbound port {inbound_port}. Testing connection...")
                try:
                    result = subprocess.run(
                        ["curl.exe", "-s", "-x", f"socks5h://127.0.0.1:{inbound_port}", "https://api.ipify.org"],
                        capture_output=True, text=True, timeout=10
                    )
                    print(f"VPN IP: {result.stdout}")
                    if result.returncode == 0 and result.stdout.strip():
                        print("✅ End-to-end VPN traffic verified successfully!")
                    else:
                        print(f"❌ Curl failed. Exit code: {result.returncode}, Error: {result.stderr}")
                except Exception as e:
                    print(f"❌ Failed to run curl: {e}")
            else:
                print("No local inbound port found in the config to test routing. Assuming sing-box uses TUN interface directly. Please test manually.")
                
        finally:
            print("Cleaning up sing-box...")
            process.terminate()
            process.wait(timeout=5)
            print("E2E Test Complete.")

if __name__ == "__main__":
    asyncio.run(main())
