"""
test_repository_exceptions.py — Tests for BaseRepository exception translation.
Verifies decouple from HTTP and translation of SQLAlchemy errors to domain exceptions.
"""
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DuplicateEntityError, EntityNotFoundError, DatabaseOperationError
from app.models import AccountStatus
from app.repositories import AccountRepository


@pytest.mark.asyncio
async def test_integrity_error_translates_to_duplicate_entity_error(account_factory):
    await account_factory(account_id="EXC-DUP-01", master_token_hash="hash_exc_dup_1")
    with pytest.raises(DuplicateEntityError) as exc_info:
        await account_factory(account_id="EXC-DUP-01", master_token_hash="hash_exc_dup_2")
    assert "Duplicate entry or constraint violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_missing_entity_raises_entity_not_found_error(db_session: AsyncSession):
    repo = AccountRepository(db_session)
    missing_id = uuid.uuid4()
    with pytest.raises(EntityNotFoundError) as exc_info:
        await repo.get_by_id_or_raise(missing_id)
    assert f"Account with ID {missing_id} not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_unexpected_sql_error_on_create_translates_to_database_operation_error(db_session: AsyncSession):
    repo = AccountRepository(db_session)
    # Mock session.commit to raise an arbitrary SQLAlchemyError
    with patch.object(db_session, "commit", new_callable=AsyncMock) as mock_commit:
        mock_commit.side_effect = SQLAlchemyError("Simulated database connection failure")
        with pytest.raises(DatabaseOperationError) as exc_info:
            await repo.create(
                account_id="FAIL-CREATE",
                master_token_hash="hash_fail",
                status=AccountStatus.ACTIVE,
            )
        assert "Database error while creating Account" in str(exc_info.value)


@pytest.mark.asyncio
async def test_unexpected_sql_error_on_get_translates_to_database_operation_error(db_session: AsyncSession):
    repo = AccountRepository(db_session)
    with patch.object(db_session, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = SQLAlchemyError("Simulated query timeout")
        with pytest.raises(DatabaseOperationError) as exc_info:
            await repo.get_by_id(uuid.uuid4())
        assert "Database error querying Account by ID" in str(exc_info.value)
