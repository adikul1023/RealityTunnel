import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from unittest.mock import AsyncMock

from app.main import app
from app.services.credential_service import CredentialService

@pytest.fixture
def override_credential_service(monkeypatch):
    mock_service = AsyncMock(spec=CredentialService)
    # Simulate a database error happening deep in the service
    mock_service.get_credentials.side_effect = SQLAlchemyError("CRITICAL_DB_LEAK_STRING")
    mock_service.revoke_credentials.side_effect = Exception("CRITICAL_UNKNOWN_LEAK_STRING")
    
    # Override the dependency
    from app.dependencies import get_credential_service
    app.dependency_overrides[get_credential_service] = lambda: mock_service
    
    # Also override auth to pass immediately
    from app.dependencies import get_current_account
    from app.models import Account
    dummy_account = Account(id=uuid.uuid4())
    app.dependency_overrides[get_current_account] = lambda: dummy_account
    
    yield mock_service
    
    app.dependency_overrides.clear()

def test_sqlalchemy_error_does_not_leak_to_http(override_credential_service):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/credentials")
    
    assert response.status_code == 500 or response.status_code == 400
    resp_text = response.text
    
    # The actual database error string MUST NOT be in the HTTP response
    assert "CRITICAL_DB_LEAK_STRING" not in resp_text
    
    # A generic message should be present instead
    assert "error" in resp_text.lower()

def test_generic_exception_does_not_leak_to_http(override_credential_service):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/credentials/revoke")
    
    assert response.status_code == 500 or response.status_code == 400
    resp_text = response.text
    
    # The unknown error string MUST NOT be in the HTTP response
    assert "CRITICAL_UNKNOWN_LEAK_STRING" not in resp_text
