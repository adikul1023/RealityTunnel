import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from unittest.mock import AsyncMock

from app.main import app
from app.services.credential_service import CredentialService

@pytest.fixture
def override_repositories():
    from app.dependencies import get_provisioning_repository, get_account_repository
    
    mock_prov_repo = AsyncMock()
    # Trigger a database error when fetching credentials
    mock_prov_repo.get_by_account_id.side_effect = SQLAlchemyError("CRITICAL_DB_LEAK_STRING")
    
    app.dependency_overrides[get_provisioning_repository] = lambda: mock_prov_repo
    
    mock_account_repo = AsyncMock()
    mock_account_repo.get_by_id.side_effect = SQLAlchemyError("CRITICAL_DB_LEAK_STRING")
    app.dependency_overrides[get_account_repository] = lambda: mock_account_repo
    
    # Override auth
    from app.dependencies import get_current_account
    from app.models import Account
    dummy_account = Account(id=uuid.uuid4())
    app.dependency_overrides[get_current_account] = lambda: dummy_account
    
    yield
    
    app.dependency_overrides.clear()

def test_sqlalchemy_error_does_not_leak_to_http(override_repositories):
    client = TestClient(app)
    response = client.get("/api/credentials")
    
    # Should be 400 Bad Request because CredentialServiceError maps to 400
    assert response.status_code == 400
    resp_text = response.text
    
    # The actual database error string MUST NOT be in the HTTP response
    assert "CRITICAL_DB_LEAK_STRING" not in resp_text
    
    # A generic message should be present instead
    assert "database error" in resp_text.lower()
