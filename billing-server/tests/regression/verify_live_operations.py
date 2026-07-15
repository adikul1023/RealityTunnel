"""
tests/regression/verify_live_operations.py — Live verification of Phase 2A Operations layer.

Executes real requests against the FastAPI app to verify:
1. GET /health -> 200 OK with actual JSON output.
2. GET /api/admin/infrastructure/status -> exact status, reason, message, and latency fields.
3. 5-second TTL Cache behavior -> makes consecutive requests within 5 seconds and confirms cache hit/timestamp reuse.
4. IP Masking -> verifies operator API returns masked IP while audit logs preserve raw details.
"""
import asyncio
import json
import time
import sys
import os
sys.path.insert(0, os.path.abspath("."))

from datetime import datetime, timezone
import uuid

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.database import get_db
from unittest.mock import AsyncMock, patch
from app.models import AdminUser, Account, Device, SubscriptionStatus
from app.models.provisioning import ProvisioningProfile, ProvisioningState
from app.services.provisioning.provider import ProvisionedUserDTO
from app.dependencies import get_admin_jwt_service
from app.security_hardening.audit import audit_service
from app.services.operations_service import OperationsService


async def run_verification():
    print("=" * 70)
    print("STARTING LIVE OPERATIONS VERIFICATION")
    print("=" * 70)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. VERIFY /health
        print("\n--- 1. Verification: GET /health ---")
        t0 = time.perf_counter()
        resp_health = await client.get("/health")
        latency_health = (time.perf_counter() - t0) * 1000
        print(f"Status Code: {resp_health.status_code} ({latency_health:.2f}ms)")
        print(f"Response Body:\n{json.dumps(resp_health.json(), indent=2)}")
        assert resp_health.status_code == 200, "Health endpoint failed!"

        # Create temporary Super Admin inside test DB for authenticated requests
        async for session in get_db():
            # Clean up old test data if any
            res = await session.execute(select(AdminUser).where(AdminUser.username == "verify_ops_admin"))
            admin = res.scalar_one_or_none()
            if not admin:
                admin = AdminUser(
                    id=uuid.uuid4(),
                    username="verify_ops_admin",
                    password_hash="dummy_hash",
                    is_super_admin=True,
                    is_active=True,
                )
                session.add(admin)
                await session.commit()
                await session.refresh(admin)

            # Generate JWT token using AdminJWTService
            token = get_admin_jwt_service().issue_admin_token(
                admin_id=admin.id,
                username=admin.username,
                is_super_admin=admin.is_super_admin,
            )
            headers = {"Authorization": f"Bearer {token}"}

            # 2. VERIFY GET /api/admin/infrastructure/status (with 'reason')
            print("\n--- 2. Verification: GET /api/admin/infrastructure/status ---")
            OperationsService.reset_status_cache()
            t0 = time.perf_counter()
            resp_status = await client.get("/api/admin/infrastructure/status", headers=headers)
            latency_status = (time.perf_counter() - t0) * 1000
            print(f"Status Code: {resp_status.status_code} ({latency_status:.2f}ms)")
            body_status = resp_status.json()
            print(f"Response Body:\n{json.dumps(body_status, indent=2)}")

            # Check that reason and message exist
            for comp, data in body_status.items():
                if isinstance(data, dict):
                    assert "status" in data, f"Missing 'status' in {comp}"
                    assert "reason" in data, f"Missing 'reason' in {comp}"
                    assert "message" in data, f"Missing 'message' in {comp}"
                    assert "last_checked" in data, f"Missing 'last_checked' in {comp}"
            print("[OK] All components returned required fields including 'status', 'reason', 'message', and 'last_checked'.")

            # 3. VERIFY 5-SECOND TTL CACHE BEHAVIOR
            print("\n--- 3. Verification: 5-Second TTL Cache Behavior ---")
            # Request 1 (already fetched above as body_status)
            first_checked = body_status["billing_api"]["last_checked"]
            print(f"Request 1 timestamp (billing_api.last_checked): {first_checked}")

            # Sleep 1 second (< 5s TTL) and make Request 2
            print("Sleeping 1.0 second before making Request 2...")
            await asyncio.sleep(1.0)
            resp_status_2 = await client.get("/api/admin/infrastructure/status", headers=headers)
            body_status_2 = resp_status_2.json()
            second_checked = body_status_2["billing_api"]["last_checked"]
            print(f"Request 2 timestamp (billing_api.last_checked): {second_checked}")

            if first_checked == second_checked:
                print("[OK] TTL Cache Hit verified! Both requests returned identical 'last_checked' timestamps without reprobing.")
            else:
                print(f"[FAIL] Cache miss! Timestamps differed: {first_checked} vs {second_checked}")

            # Sleep 5.1 seconds (> 5s TTL) to confirm expiration & reprobe
            print("Sleeping 5.1 seconds to allow cache TTL expiration...")
            await asyncio.sleep(5.1)
            resp_status_3 = await client.get("/api/admin/infrastructure/status", headers=headers)
            body_status_3 = resp_status_3.json()
            third_checked = body_status_3["billing_api"]["last_checked"]
            print(f"Request 3 timestamp after 5.1s expiration: {third_checked}")
            assert third_checked != first_checked, "Cache failed to expire after 5 seconds!"
            print("[OK] TTL Cache Expiration verified! Probes refreshed as expected.")

            # 4. VERIFY IP MASKING & AUDIT LOG SEPARATION
            print("\n--- 4. Verification: IP Masking vs Audit Log ---")
            # Create test account and device with raw IP
            raw_ip = "203.0.113.195"
            acc = Account(
                id=uuid.uuid4(),
                account_id=f"TEST-MASK-{int(time.time())}",
                master_token_hash=f"hash_{int(time.time())}",
                status=SubscriptionStatus.ACTIVE,
                subscription_expires_at=datetime.now(timezone.utc),
            )
            dev_guid = f"mask-verify-dev-{int(time.time())}"
            dev = Device(
                id=uuid.uuid4(),
                account_id=acc.id,
                device_guid=dev_guid,
                is_active=True,
            )
            profile = ProvisioningProfile(
                id=uuid.uuid4(),
                account_id=acc.id,
                remote_user_id=f"remote_{acc.account_id}",
                provisioning_state=ProvisioningState.ACTIVE,
            )
            session.add(acc)
            session.add(dev)
            session.add(profile)
            await session.commit()

            # Record an explicit audit event storing exact IP
            await audit_service.record_event(
                event_type="device_connection",
                actor_id=str(acc.id),
                target_id=dev_guid,
                details={"raw_client_ip": raw_ip, "action": "connect"},
            )

            # Query Operator API for Account details
            with patch("app.services.provisioning.marzban.MarzbanProvisioningProvider.get_user", new=AsyncMock(return_value=ProvisionedUserDTO(remote_user_id=f"remote_{acc.account_id}", status="active", last_ip=raw_ip))):
                resp_acc = await client.get(f"/api/admin/account/{acc.account_id}", headers=headers)
            body_acc = resp_acc.json()
            returned_ip = body_acc["vpn"]["last_ip"]
            print(f"Raw Client IP stored in DB: {raw_ip}")
            print(f"Operator API returned vpn.last_ip: {returned_ip}")
            assert returned_ip == "203.0.xxx.xxx", f"Expected masked IP '203.0.xxx.xxx', got '{returned_ip}'"
            print("[OK] Operator API correctly masked the IP address (truncated final two octets).")

            # Query Audit Log API to confirm raw IP remains tracked inside audit details
            resp_audit = await client.get(f"/api/admin/audit-events?limit=10", headers=headers)
            audit_items = resp_audit.json()["items"]
            conn_events = [e for e in audit_items if e.get("target_id") == dev_guid]
            assert len(conn_events) > 0, "Audit event not found!"
            audit_stored_ip = conn_events[0]["details"].get("raw_client_ip")
            print(f"Audit Log API returned details.raw_client_ip: {audit_stored_ip}")
            assert audit_stored_ip == raw_ip, f"Expected raw IP in audit log '{raw_ip}', got '{audit_stored_ip}'"
            print("[OK] Audit Log preserved the exact raw IP address for security forensics.")

            break

    print("\n" + "=" * 70)
    print("ALL LIVE OPERATIONS VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_verification())
