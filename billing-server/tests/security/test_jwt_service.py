"""
test_jwt_service.py — Comprehensive Unit Tests for JWTService (Phase 1.3.3)
"""
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import jwt
import pytest

from app.security import (
    AccessTokenClaims,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    JWTService,
)
from app.services.exceptions import (
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    TokenExpiredError,
    TokenNotYetValidError,
)


@pytest.fixture
def jwt_service(tmp_path: Path) -> JWTService:
    """Provide an isolated JWTService instance using a temporary keys directory."""
    return JWTService(keys_dir=tmp_path, environment="development")


def test_token_issuance_and_structure(jwt_service: JWTService):
    """Verify access token issuance, EdDSA algorithm header, and exact claim structure."""
    acc_uuid = uuid.uuid4()
    acc_id = "RT-TEST-ISSU-0001"
    dev_guid = "dev_guid_hex_string_12345"

    token = jwt_service.issue_access_token(acc_uuid, acc_id, dev_guid)
    assert isinstance(token, str) and len(token) > 0

    # Inspect unverified header and payload to confirm exact structure
    header = jwt.get_unverified_header(token)
    assert header.get("alg") == "EdDSA"
    assert header.get("typ") == "JWT"

    unverified_payload = jwt.decode(token, options={"verify_signature": False})
    assert unverified_payload["sub"] == str(acc_uuid)
    assert unverified_payload["account"] == acc_id
    assert unverified_payload["device"] == dev_guid
    assert unverified_payload["iss"] == JWT_ISSUER
    assert unverified_payload["aud"] == JWT_AUDIENCE
    assert "jti" in unverified_payload and len(unverified_payload["jti"]) == 32

    # Verify expiration is ~15 minutes after iat
    iat = unverified_payload["iat"]
    exp = unverified_payload["exp"]
    assert exp - iat == ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_verify_valid_token(jwt_service: JWTService):
    """Verify that a valid token decodes successfully into typed AccessTokenClaims."""
    acc_uuid = uuid.uuid4()
    token = jwt_service.issue_access_token(acc_uuid, "RT-VALID-0001", "device_guid_01")

    claims = jwt_service.verify_access_token(token)
    assert isinstance(claims, AccessTokenClaims)
    assert claims.sub == str(acc_uuid)
    assert claims.account == "RT-VALID-0001"
    assert claims.device == "device_guid_01"
    assert claims.iss == JWT_ISSUER
    assert claims.aud == JWT_AUDIENCE


def test_verify_expired_token(jwt_service: JWTService):
    """Verify that an expired token raises TokenExpiredError."""
    now = int(datetime.now(timezone.utc).timestamp())
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "account": "RT-EXPIRED-001",
        "device": "dev_guid",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now - 3600,
        "nbf": now - 3600,
        "exp": now - 10,  # Expired 10 seconds ago
        "jti": "jti_expired_test",
    }
    token = jwt.encode(expired_payload, jwt_service.private_key, algorithm=JWT_ALGORITHM)

    with pytest.raises(TokenExpiredError) as exc_info:
        jwt_service.verify_access_token(token)
    assert "expired" in str(exc_info.value).lower()


def test_verify_wrong_issuer(jwt_service: JWTService):
    """Verify that a token with an incorrect issuer raises InvalidIssuerError."""
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": str(uuid.uuid4()),
        "account": "RT-WRONG-ISS",
        "device": "dev_guid",
        "iss": "https://evil-issuer.example.com",
        "aud": JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + 900,
        "jti": "jti_iss_test",
    }
    token = jwt.encode(payload, jwt_service.private_key, algorithm=JWT_ALGORITHM)

    with pytest.raises(InvalidIssuerError) as exc_info:
        jwt_service.verify_access_token(token)
    assert "issuer" in str(exc_info.value).lower()


def test_verify_wrong_audience(jwt_service: JWTService):
    """Verify that a token with an incorrect audience raises InvalidAudienceError."""
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": str(uuid.uuid4()),
        "account": "RT-WRONG-AUD",
        "device": "dev_guid",
        "iss": JWT_ISSUER,
        "aud": "https://evil-audience.example.com",
        "iat": now,
        "nbf": now,
        "exp": now + 900,
        "jti": "jti_aud_test",
    }
    token = jwt.encode(payload, jwt_service.private_key, algorithm=JWT_ALGORITHM)

    with pytest.raises(InvalidAudienceError) as exc_info:
        jwt_service.verify_access_token(token)
    assert "audience" in str(exc_info.value).lower()


def test_verify_malformed_jwt(jwt_service: JWTService):
    """Verify that malformed string tokens raise InvalidTokenError."""
    with pytest.raises(InvalidTokenError):
        jwt_service.verify_access_token("not.a.valid.jwt.token")

    with pytest.raises(InvalidTokenError):
        jwt_service.verify_access_token("completely_invalid_string")


def test_verify_tampered_payload(jwt_service: JWTService):
    """Verify that tampering with the payload invalidates the signature and raises InvalidSignatureError."""
    token = jwt_service.issue_access_token(uuid.uuid4(), "RT-TAMPER-001", "device_guid")
    parts = token.split(".")
    assert len(parts) == 3

    # Tamper with the middle payload segment by changing a character
    tampered_payload = parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B")
    tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

    with pytest.raises(InvalidSignatureError):
        jwt_service.verify_access_token(tampered_token)


def test_verify_tampered_signature(jwt_service: JWTService):
    """Verify that modifying the signature segment raises InvalidSignatureError."""
    token = jwt_service.issue_access_token(uuid.uuid4(), "RT-TAMPSIG-01", "device_guid")
    parts = token.split(".")
    
    # Replace signature segment with bogus base64url string
    bogus_sig = "A" * len(parts[2])
    tampered_token = f"{parts[0]}.{parts[1]}.{bogus_sig}"

    with pytest.raises(InvalidSignatureError):
        jwt_service.verify_access_token(tampered_token)


def test_verify_future_nbf(jwt_service: JWTService):
    """Verify that a token with a Not Before (nbf) timestamp in the future raises TokenNotYetValidError."""
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": str(uuid.uuid4()),
        "account": "RT-FUTURE-NBF",
        "device": "dev_guid",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "nbf": now + 3600,  # Valid 1 hour in the future
        "exp": now + 7200,
        "jti": "jti_nbf_test",
    }
    token = jwt.encode(payload, jwt_service.private_key, algorithm=JWT_ALGORITHM)

    with pytest.raises(TokenNotYetValidError) as exc_info:
        jwt_service.verify_access_token(token)
    assert "not yet valid" in str(exc_info.value).lower()


def test_verify_missing_required_claim(jwt_service: JWTService):
    """Verify that missing required claims (e.g., 'device' or 'account') raise InvalidTokenError."""
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": str(uuid.uuid4()),
        # missing "account" and "device"
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + 900,
        "jti": "jti_missing_test",
    }
    token = jwt.encode(payload, jwt_service.private_key, algorithm=JWT_ALGORITHM)

    with pytest.raises(InvalidTokenError) as exc_info:
        jwt_service.verify_access_token(token)
    assert "missing required jwt claim" in str(exc_info.value).lower()


def test_key_handling_and_isolation(tmp_path: Path):
    """
    Verify key management:
    1. Development auto-generation creates both private and public PEM files.
    2. Public key verifies tokens issued by private key.
    3. Different keypair cannot verify tokens from another service instance.
    4. Production mode forbids auto-generation when keys are absent.
    """
    dir1 = tmp_path / "keys1"
    service1 = JWTService(keys_dir=dir1, environment="development")
    assert (dir1 / "ed25519_private.pem").exists()
    assert (dir1 / "ed25519_public.pem").exists()

    token1 = service1.issue_access_token(uuid.uuid4(), "RT-KEYTEST-01", "dev_01")
    claims1 = service1.verify_access_token(token1)
    assert claims1.account == "RT-KEYTEST-01"

    # Second service instance with entirely different keypair
    dir2 = tmp_path / "keys2"
    service2 = JWTService(keys_dir=dir2, environment="development")

    # Service 2 attempting to verify Token 1 should fail due to signature mismatch
    with pytest.raises(InvalidSignatureError):
        service2.verify_access_token(token1)

    # Production mode without existing keys must raise RuntimeError
    dir_prod = tmp_path / "keys_prod"
    with pytest.raises(RuntimeError) as exc_info:
        JWTService(keys_dir=dir_prod, environment="production")
    assert "production ed25519 signing keys are absent" in str(exc_info.value).lower()


def test_verify_algorithm_confusion_hs256(jwt_service: JWTService):
    """
    Verify algorithm confusion defense:
    Attempting to validate an HS256 token against the Ed25519 public key must fail immediately.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": str(uuid.uuid4()),
        "account": "RT-CONFUSE-01",
        "device": "dev_guid",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + 900,
        "jti": "jti_hs256_test",
    }
    # Encode with HS256 using a symmetric secret
    hs256_token = jwt.encode(payload, "symmetric_secret_key", algorithm="HS256")

    with pytest.raises(InvalidTokenError) as exc_info:
        jwt_service.verify_access_token(hs256_token)
    assert "algorithm" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


def test_key_loading_partial_existence_edge_case(tmp_path: Path):
    """
    Verify behavior when only one key file exists (e.g. private exists, public missing):
    1. Production mode must fail immediately with RuntimeError.
    2. Development mode must cleanly regenerate both matching files without regenerating just one half.
    """
    dir_partial = tmp_path / "keys_partial"
    dir_partial.mkdir()
    private_file = dir_partial / "ed25519_private.pem"
    # Write dummy content so only private file exists
    private_file.write_bytes(b"dummy private pem content")

    # In production, partial existence must fail immediately
    with pytest.raises(RuntimeError) as exc_info:
        JWTService(keys_dir=dir_partial, environment="production")
    assert "production ed25519 signing keys are absent" in str(exc_info.value).lower()

    # In development, partial existence cleanly regenerates a fresh valid keypair
    service_dev = JWTService(keys_dir=dir_partial, environment="development")
    assert private_file.exists()
    assert (dir_partial / "ed25519_public.pem").exists()
    assert private_file.read_bytes() != b"dummy private pem content"

    # Verify the newly generated keypair issues and verifies valid tokens
    token = service_dev.issue_access_token(uuid.uuid4(), "RT-PARTIAL-01", "dev_guid")
    claims = service_dev.verify_access_token(token)
    assert claims.account == "RT-PARTIAL-01"
