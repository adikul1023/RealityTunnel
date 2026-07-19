"""
test_jwt_rotation.py — Integration tests for JWT Key Rotation drill.
Proves that when the primary JWT secret is rotated, old refresh tokens are safely rejected
while new logins succeed.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings


pytestmark = pytest.mark.asyncio

async def test_jwt_key_rotation_drill(
    async_client: AsyncClient,
    account_factory,
    db_session: AsyncSession
):
    """
    1. Login with the old key, get an access token and refresh token.
    2. Rotate the JWT_SECRET (simulate by modifying settings).
    3. Old access token and old refresh token should FAIL.
    4. New login should succeed and yield new working tokens.
    """
    from app.security import hash_master_token
    master_token = "a" * 64
    master_token_hash = hash_master_token(master_token)
    
    # Create customer account
    account = await account_factory(account_id="RT-JWT-0001", master_token_hash=master_token_hash)

    # 1. Standard login
    resp = await async_client.post("/api/auth/login", json={
        "account_id": "RT-JWT-0001",
        "master_token": master_token,
        "device_guid": "device-jwt-123"
    })
    assert resp.status_code == 200
    tokens = resp.json()
    old_access = tokens["access_token"]
    old_refresh = tokens["refresh_token"]

    # Verify old access works
    resp = await async_client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_access}"})
    assert resp.status_code == 200

    # Verify old refresh works
    resp = await async_client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200

    # 2. ROTATE THE KEY (simulate env change)
    from app.dependencies import get_jwt_service, get_admin_jwt_service
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    from app.main import app
    
    # Generate new keypair
    new_private = ed25519.Ed25519PrivateKey.generate()
    new_public = new_private.public_key()
    
    # Override the JWTService and AdminJWTService instances in dependency overrides
    # (Assuming we can just patch the singleton instance or dependency)
    # Actually, the easiest way is to patch the service instance used by the routes.
    import pytest
    from app.security.jwt_service import JWTService
    from app.security.admin_jwt import AdminJWTService
    
    original_jwt_service = app.dependency_overrides.get(get_jwt_service)
    original_admin_jwt_service = app.dependency_overrides.get(get_admin_jwt_service)
    
    new_jwt_service = JWTService(environment="development")
    new_jwt_service.private_key = new_private
    new_jwt_service.public_key = new_public
    
    new_admin_jwt_service = AdminJWTService(environment="development")
    new_admin_jwt_service.private_key = new_private
    new_admin_jwt_service.public_key = new_public

    app.dependency_overrides[get_jwt_service] = lambda: new_jwt_service
    app.dependency_overrides[get_admin_jwt_service] = lambda: new_admin_jwt_service

    try:
        # 3. Old tokens should now fail signature verification
        resp = await async_client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_access}"})
        assert resp.status_code == 401, "Old access token should be rejected after rotation"

        resp = await async_client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 401, "Old refresh token should be rejected after rotation"

        # 4. New login with new key
        resp = await async_client.post("/api/auth/login", json={
            "account_id": "RT-JWT-0001",
            "master_token": master_token,
            "device_guid": "device-jwt-123"
        })
        assert resp.status_code == 200
        new_tokens = resp.json()
        new_access = new_tokens["access_token"]
        new_refresh = new_tokens["refresh_token"]

        # New tokens should work
        resp = await async_client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
        assert resp.status_code == 200

        resp = await async_client.post("/api/auth/refresh", json={"refresh_token": new_refresh})
        assert resp.status_code == 200

    finally:
        # Restore original for other tests
        if original_jwt_service:
            app.dependency_overrides[get_jwt_service] = original_jwt_service
        else:
            app.dependency_overrides.pop(get_jwt_service, None)
            
        if original_admin_jwt_service:
            app.dependency_overrides[get_admin_jwt_service] = original_admin_jwt_service
        else:
            app.dependency_overrides.pop(get_admin_jwt_service, None)
