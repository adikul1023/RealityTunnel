import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from unittest.mock import AsyncMock

from app.main import app
from app.services.credential_service import CredentialService

@pytest.fixture
def override_repositories():
    from app.dependencies import get_credential_service, get_current_account
    
    mock_prov_svc = AsyncMock()
    mock_prov_svc.get_provisioned_user.side_effect = SQLAlchemyError("CRITICAL_DB_LEAK_STRING")
    
    # We must construct a real CredentialService because overriding provisioning_service
    # makes get_credential_service return a mock due to the `if provisioning_service.credential_service` check.
    from app.services.credential_service import CredentialService
    real_cred_svc = CredentialService(session=AsyncMock(), provisioning_service=mock_prov_svc)
    
    app.dependency_overrides[get_credential_service] = lambda: real_cred_svc
    
    # Override auth
    from app.models import Account
    dummy_account = Account(id=uuid.uuid4())
    app.dependency_overrides[get_current_account] = lambda: dummy_account
    
    yield
    
    app.dependency_overrides.clear()

def test_sqlalchemy_error_does_not_leak_to_http(override_repositories):
    client = TestClient(app)
    response = client.get("/api/credentials")
    
    # Should be 400 Bad Request because CredentialServiceError maps to 400 in the router
    assert response.status_code == 400
    resp_text = response.text
    
    # The actual database error string MUST NOT be in the HTTP response
    assert "CRITICAL_DB_LEAK_STRING" not in resp_text
    
    # A generic message should be present instead
    assert "database error" in resp_text.lower()
