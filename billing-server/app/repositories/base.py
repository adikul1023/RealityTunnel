"""
base.py — Generic BaseRepository providing reusable async CRUD helpers.
"""
from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base
from app.exceptions import (
    DuplicateEntityError,
    DatabaseOperationError,
    EntityNotFoundError,
)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository providing core CRUD operations for SQLAlchemy models.
    Translates SQLAlchemy exceptions into domain-specific exceptions.
    """

    def __init__(self, model_class: type[ModelType], session: AsyncSession) -> None:
        self.model_class = model_class
        self.session = session

    async def create(self, entity: ModelType | None = None, *, commit: bool = True, **kwargs: Any) -> ModelType:
        """
        Persist a new entity to the database.
        Accepts either an instantiated model object or keyword arguments.
        If commit=False, flushes the session without committing the transaction.
        """
        if entity is None:
            entity = self.model_class(**kwargs)
        self.session.add(entity)
        try:
            if commit:
                await self.session.commit()
                await self.session.refresh(entity)
            else:
                await self.session.flush()
            return entity
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateEntityError(
                f"Duplicate entry or constraint violation for {self.model_class.__name__}"
            ) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseOperationError(
                f"Database error while creating {self.model_class.__name__}"
            ) from exc

    async def get_by_id(self, entity_id: uuid.UUID | str | int, *, for_update: bool = False) -> ModelType | None:
        """Retrieve an entity by its primary key ID."""
        try:
            return await self.session.get(self.model_class, entity_id, with_for_update=for_update)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                f"Database error querying {self.model_class.__name__} by ID"
            ) from exc

    async def get_by_id_or_raise(self, entity_id: uuid.UUID | str | int, *, for_update: bool = False) -> ModelType:
        """Retrieve an entity by ID or raise EntityNotFoundError if missing."""
        entity = await self.get_by_id(entity_id, for_update=for_update)
        if entity is None:
            raise EntityNotFoundError(
                f"{self.model_class.__name__} with ID {entity_id} not found"
            )
        return entity

    async def update(self, entity: ModelType, *, commit: bool = True, **kwargs: Any) -> ModelType:
        """Update attribute values on an existing entity and commit/flush changes."""
        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        try:
            if commit:
                await self.session.commit()
                await self.session.refresh(entity)
            else:
                await self.session.flush()
            return entity
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateEntityError(
                f"Constraint violation while updating {self.model_class.__name__}"
            ) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseOperationError(
                f"Database error updating {self.model_class.__name__}"
            ) from exc

    async def delete(self, entity_id_or_obj: uuid.UUID | str | int | ModelType, *, commit: bool = True) -> bool:
        """
        Delete an entity by ID or object reference.
        Returns True if deleted, False if not found.
        """
        if isinstance(entity_id_or_obj, self.model_class):
            entity = entity_id_or_obj
        else:
            entity = await self.get_by_id(entity_id_or_obj)
        if not entity:
            return False
        try:
            await self.session.delete(entity)
            if commit:
                await self.session.commit()
            else:
                await self.session.flush()
            return True
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseOperationError(
                f"Database error deleting {self.model_class.__name__}"
            ) from exc

    async def exists(self, **kwargs: Any) -> bool:
        """
        Check if at least one row matching the keyword arguments exists.
        Performs an indexed existence check without counting rows.
        """
        try:
            stmt = select(self.model_class).filter_by(**kwargs).limit(1)
            result = await self.session.execute(stmt)
            return result.first() is not None
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                f"Database error checking existence in {self.model_class.__name__}"
            ) from exc
