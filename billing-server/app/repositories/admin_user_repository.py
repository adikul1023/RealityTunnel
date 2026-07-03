"""
admin_user_repository.py — Persistence layer for AdminUser entities.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseOperationError
from app.models import AdminUser
from app.repositories.base import BaseRepository


class AdminUserRepository(BaseRepository[AdminUser]):
    """
    Repository for AdminUser model queries and CRUD operations.
    Encapsulates all database interactions for administrative accounts.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AdminUser, session)

    async def get_by_username(self, username: str) -> AdminUser | None:
        """Retrieve an admin user by their unique username."""
        try:
            stmt = select(AdminUser).where(AdminUser.username == username)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                "Database error querying AdminUser by username"
            ) from exc
