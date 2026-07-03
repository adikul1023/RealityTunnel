"""
dependencies.py — Centralized dependency injection providers for OverREALITY API services.

Encapsulates database session wiring and service instantiation so routers never touch
repositories or SQLAlchemy sessions directly. Also provides JWT bearer token authentication
and active account context for protected endpoints.
"""
from __future__ import annotations

import logging
import uuid
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.account import Account
from app.repositories import (
    AccountRepository,
    DeviceRepository,
    RefreshTokenRepository,
    ConnectionSignalRepository,
)
from app.security import JWTService
from app.services import (
    AuthenticationService,
    DeviceService,
    RefreshTokenService,
    ConnectionSignalService,
)

logger = logging.getLogger(__name__)

# Bearer authentication scheme for OpenAPI Swagger documentation
oauth2_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuthentication",
    description="Enter Ed25519 Access JWT",
)

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


async def get_device_repo(session: AsyncSession = Depends(get_db)) -> DeviceRepository:
    """Dependency provider yielding DeviceRepository tied to the request session."""
    return DeviceRepository(session)


async def get_device_service(
    device_repo: DeviceRepository = Depends(get_device_repo),
    account_repo: AccountRepository = Depends(get_account_repo),
) -> DeviceService:
    """Dependency provider yielding DeviceService."""
    return DeviceService(device_repo, account_repo)


async def get_signal_repo(
    session: AsyncSession = Depends(get_db),
) -> ConnectionSignalRepository:
    """Dependency provider yielding ConnectionSignalRepository tied to request session."""
    return ConnectionSignalRepository(session)


async def get_signal_service(
    signal_repo: ConnectionSignalRepository = Depends(get_signal_repo),
) -> ConnectionSignalService:
    """Dependency provider yielding ConnectionSignalService."""
    return ConnectionSignalService(signal_repo)



async def get_current_account(
    request: Request,
    _bearer: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
    auth_service: AuthenticationService = Depends(get_auth_service),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> Account:
    """
    Dependency yielding the authenticated and validated Account model from an HTTP Authorization Bearer token.

    Requires Authorization: Bearer <token>. Rejects missing header, malformed header, missing Bearer prefix,
    empty token, invalid/expired JWT, or inactive backing accounts with clean HTTP 401 Unauthorized responses.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.info("Authentication failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or token invalid",
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        logger.info("Authentication failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or token invalid",
        )

    token = parts[1].strip()
    if not token:
        logger.info("Authentication failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or token invalid",
        )

    try:
        claims = jwt_service.verify_access_token(token)
    except Exception:
        logger.info("Token invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or token invalid",
        )

    try:
        account = await auth_service.get_active_account_by_uuid(uuid.UUID(claims.sub))
    except Exception:
        logger.info("Authentication failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or token invalid",
        )

    logger.info("Authentication succeeded")
    return account
