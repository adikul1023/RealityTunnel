"""
provisioning_repository.py — Persistence layer for ProvisioningProfile entities (Phase 2.2).
"""
from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models import ProvisioningProfile
from app.repositories.base import BaseRepository


class ProvisioningRepository(BaseRepository[ProvisioningProfile]):
    """
    Repository for ProvisioningProfile queries and CRUD operations.
    Supports row-level locking for concurrency control during VPN provisioning synchronization.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ProvisioningProfile, session)

    async def get_by_account_id(
        self, account_id: uuid.UUID, *, for_update: bool = False
    ) -> ProvisioningProfile | None:
        """
        Retrieve the provisioning profile associated with an account ID.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            stmt = select(ProvisioningProfile).where(ProvisioningProfile.account_id == account_id)
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying provisioning profile by account ID"
            ) from exc

    async def get_by_remote_user_id(
        self, remote_user_id: str, *, for_update: bool = False
    ) -> ProvisioningProfile | None:
        """
        Retrieve the provisioning profile associated with a remote user ID (e.g., Marzban username).
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            stmt = select(ProvisioningProfile).where(ProvisioningProfile.remote_user_id == remote_user_id)
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying provisioning profile by remote user ID"
            ) from exc
