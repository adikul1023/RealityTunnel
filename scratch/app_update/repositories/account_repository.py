"""
account_repository.py — Persistence layer for Account entities.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models import Account
from app.repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account]):
    """
    Repository for Account model queries and CRUD operations.
    Encapsulates all database interactions for accounts.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Account, session)

    async def get_by_account_id(
        self, account_id: str, *, for_update: bool = False
    ) -> Account | None:
        """
        Retrieve an account by its unique human-readable account ID.
        If for_update=True, acquires a row-level exclusive lock (SELECT ... FOR UPDATE),
        matching the pattern used by SubscriptionRepository/PaymentRepository/DeviceRepository
        (Finding H-4).
        """
        try:
            stmt = select(Account).where(Account.account_id == account_id)
            if for_update:
                stmt = stmt.with_for_update()
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying Account by account_id"
            ) from exc

    async def get_by_marzban_username(self, username: str) -> Account | None:
        """Retrieve an account by its Server 2 Marzban username."""
        try:
            stmt = select(Account).where(Account.marzban_username == username)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying Account by marzban_username"
            ) from exc

    async def get_by_master_token_hash(self, token_hash: str) -> Account | None:
        """Retrieve an account by its SHA-256 Master Token digest."""
        try:
            stmt = select(Account).where(Account.master_token_hash == token_hash)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying Account by master_token_hash"
            ) from exc

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[Account]:
        """Return a paginated list of accounts ordered by creation date descending."""
        from sqlalchemy import desc

        try:
            stmt = (
                select(Account)
                .order_by(desc(Account.created_at))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Database error listing accounts") from exc

    async def count_all(self) -> int:
        """Return total number of accounts."""
        try:
            stmt = select(func.count()).select_from(Account)
            result = await self.session.execute(stmt)
            return int(result.scalar_one() or 0)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError("Database error counting accounts") from exc
