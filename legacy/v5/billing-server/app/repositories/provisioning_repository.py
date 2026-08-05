"""
provisioning_repository.py — Persistence layer for ProvisioningProfile entities (Phase 2.2).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models import ProvisioningProfile
from app.models.provisioning import ProvisioningState
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

    async def get_suspended_profiles(
        self, *, for_update: bool = False
    ) -> list[ProvisioningProfile]:
        """
        Retrieve all provisioning profiles in SUSPENDED state.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            from app.models.provisioning import ProvisioningState
            stmt = select(ProvisioningProfile).where(
                ProvisioningProfile.provisioning_state == ProvisioningState.SUSPENDED
            )
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying suspended provisioning profiles"
            ) from exc

    async def get_all_active_or_suspended(
        self, *, for_update: bool = False, skip_locked: bool = False
    ) -> list[ProvisioningProfile]:
        """
        Retrieve all provisioning profiles not in TERMINATED state.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            from app.models.provisioning import ProvisioningState
            stmt = select(ProvisioningProfile).where(
                ProvisioningProfile.provisioning_state != ProvisioningState.TERMINATED
            )
            if for_update:
                stmt = stmt.with_for_update(skip_locked=skip_locked)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying active or suspended provisioning profiles"
            ) from exc

    async def get_stale_profiles(
        self, cutoff: datetime, *, for_update: bool = False, skip_locked: bool = False
    ) -> list[ProvisioningProfile]:
        """
        Retrieve ACTIVE or SUSPENDED provisioning profiles synced at or before cutoff.
        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
        """
        try:
            from app.models.provisioning import ProvisioningState
            stmt = (
                select(ProvisioningProfile)
                .where(ProvisioningProfile.provisioning_state != ProvisioningState.TERMINATED)
                .where(ProvisioningProfile.last_sync_at <= cutoff)
            )
            if for_update:
                stmt = stmt.with_for_update(skip_locked=skip_locked)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying stale provisioning profiles"
            ) from exc

    async def list_all_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        state: ProvisioningState | None = None,
    ) -> list[ProvisioningProfile]:
        """
        Retrieve a paginated list of all provisioning profiles across all accounts.
        Optionally filter by provisioning state.
        """
        try:
            stmt = select(ProvisioningProfile).order_by(ProvisioningProfile.created_at.desc()).limit(limit).offset(offset)
            if state is not None:
                stmt = stmt.where(ProvisioningProfile.provisioning_state == state)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying paginated provisioning profiles"
            ) from exc

    async def count_all(self, state: ProvisioningState | None = None) -> int:
        """
        Count total provisioning profiles across all accounts, optionally filtered by state.
        """
        try:
            stmt = select(func.count()).select_from(ProvisioningProfile)
            if state is not None:
                stmt = stmt.where(ProvisioningProfile.provisioning_state == state)
            result = await self.session.execute(stmt)
            return int(result.scalar_one() or 0)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error counting provisioning profiles"
            ) from exc


