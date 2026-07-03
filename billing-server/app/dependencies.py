"""
dependencies.py — Centralized dependency injection providers for OverREALITY API services.

Encapsulates database session wiring and service instantiation so routers never touch
repositories or SQLAlchemy sessions directly.
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import AccountRepository, RefreshTokenRepository
from app.security import JWTService
from app.services import AuthenticationService, RefreshTokenService

# Singleton JWT service instance (stateless Ed25519 signer/verifier)
# Instantiated once on first request; loads keys from disk once and never regenerates.
_jwt_service: JWTService | None = None


def get_jwt_service() -> JWTService:
    """Dependency provider yielding the stateless singleton JWTService."""
    global _jwt_service
    if _jwt_service is None:
        _jwt_service = JWTService()
    return _jwt_service


async def get_account_repo(session: AsyncSession = Depends(get_db)) -> AccountRepository:
    """Dependency provider yielding AccountRepository tied to the request session."""
    return AccountRepository(session)


async def get_refresh_repo(session: AsyncSession = Depends(get_db)) -> RefreshTokenRepository:
    """Dependency provider yielding RefreshTokenRepository tied to the request session."""
    return RefreshTokenRepository(session)


async def get_auth_service(
    account_repo: AccountRepository = Depends(get_account_repo),
) -> AuthenticationService:
    """Dependency provider yielding AuthenticationService."""
    return AuthenticationService(account_repo)


async def get_refresh_service(
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_repo),
) -> RefreshTokenService:
    """Dependency provider yielding RefreshTokenService."""
    return RefreshTokenService(refresh_repo)
