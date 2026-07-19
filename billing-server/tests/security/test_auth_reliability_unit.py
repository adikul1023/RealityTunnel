"""
Unit tests verifying Phase 9.1.4 Authentication Reliability fixes:
- Credential normalization in AuthenticationService.authenticate
- Precise failure details in get_current_account dependency
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request

from app.models.account import Account
from app.models.base import AccountStatus
from app.services.authentication import AuthenticationService, AuthenticationReason
from app.security import hash_master_token
from app.dependencies import get_current_account
from app.services.exceptions import TokenExpiredError, InvalidSignatureError


@pytest.mark.asyncio
async def test_authentication_service_normalizes_credentials():
    mock_repo = AsyncMock()
    account_id = "ST-ABCD-1234"
    master_token = "secret_token_123"
    token_hash = hash_master_token(master_token)

    mock_account = Account(
        id=uuid.uuid4(),
        account_id=account_id,
        master_token_hash=token_hash,
        status=AccountStatus.ACTIVE,
    )
    mock_repo.get_by_account_id.return_value = mock_account

    service = AuthenticationService(mock_repo)

    # Pass account ID in lowercase with whitespace and master token with whitespace
    result = await service.authenticate("  st-abcd-1234 \n", f"  {master_token}  ")

    assert result.success is True
    assert result.reason == AuthenticationReason.SUCCESS
    assert result.account == mock_account
    mock_repo.get_by_account_id.assert_called_once_with("ST-ABCD-1234")


@pytest.mark.asyncio
async def test_get_current_account_missing_header():
    request = MagicMock(spec=Request)
    request.headers.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_current_account(
            request=request,
            _bearer=None,
            auth_service=AsyncMock(),
            jwt_service=AsyncMock(),
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing Authorization header"


@pytest.mark.asyncio
async def test_get_current_account_expired_token():
    request = MagicMock(spec=Request)
    request.headers.get.return_value = "Bearer some.token.here"

    mock_jwt = MagicMock()
    mock_jwt.verify_access_token.side_effect = TokenExpiredError("Expired")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_account(
            request=request,
            _bearer=None,
            auth_service=AsyncMock(),
            jwt_service=mock_jwt,
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Access token has expired"


@pytest.mark.asyncio
async def test_get_current_account_invalid_signature():
    request = MagicMock(spec=Request)
    request.headers.get.return_value = "Bearer some.token.here"

    mock_jwt = MagicMock()
    mock_jwt.verify_access_token.side_effect = InvalidSignatureError("Signature mismatch")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_account(
            request=request,
            _bearer=None,
            auth_service=AsyncMock(),
            jwt_service=mock_jwt,
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid access token signature"

