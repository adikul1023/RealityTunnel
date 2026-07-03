"""
refresh_token_repository.py — Persistence layer for RefreshToken entities.
"""
from __future__ import annotations

import uuid
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """
    Repository for RefreshToken model queries and operations.
    Supports secure Refresh Token Rotation (RTR) and bulk session revocation.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Retrieve a refresh token by its SHA-256 digest."""
        try:
            stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying RefreshToken by token_hash"
            ) from exc

    async def revoke(self, token_hash: str, *, commit: bool = True) -> bool:
        """
        Revoke a single refresh token by marking is_revoked = True.
        Returns True if the token existed and was revoked, False if not found.
        If commit=False, flushes the session without committing the transaction.
        """
        try:
            stmt = (
                update(RefreshToken)
                .where(RefreshToken.token_hash == token_hash, RefreshToken.is_revoked == False)
                .values(is_revoked=True)
            )
            result = await self.session.execute(stmt)
            if commit:
                await self.session.commit()
            else:
                await self.session.flush()
            return result.rowcount > 0
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseOperationError(
                "Database error revoking RefreshToken"
            ) from exc

    async def revoke_all_for_account(self, account_id: uuid.UUID, *, commit: bool = True) -> int:
        """
        Revoke all active refresh tokens for a given account.
        Returns the number of sessions that were newly revoked.
        If commit=False, flushes the session without committing the transaction.
        """
        try:
            stmt = (
                update(RefreshToken)
                .where(RefreshToken.account_id == account_id, RefreshToken.is_revoked == False)
                .values(is_revoked=True)
            )
            result = await self.session.execute(stmt)
            if commit:
                await self.session.commit()
            else:
                await self.session.flush()
            return result.rowcount
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseOperationError(
                "Database error revoking all refresh tokens for account"
            ) from exc
