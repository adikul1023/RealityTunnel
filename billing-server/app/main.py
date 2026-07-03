"""
RealityTunnel Billing/Auth Server
Phase 1.3.5 — Authentication & Refresh API Endpoints
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import engine, verify_db
from app.exceptions import DuplicateEntityError, EntityNotFoundError, RepositoryError
from app.routers import auth, health
from app.services.exceptions import (
    AuthenticationServiceError,
    AccountNotActiveError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenReplayError,
    RefreshTokenRevokedError,
    RefreshTokenServiceError,
    ServiceError,
    TokenExpiredError,
    TokenNotYetValidError,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup / shutdown lifecycle."""
    logger.info("Billing server starting up…")
    logger.info("Database URL: %s", settings.database_url_safe)
    yield
    logger.info("Billing server shutting down…")
    await engine.dispose()


app = FastAPI(
    title="RealityTunnel Billing/Auth API",
    description="Billing & authentication backend for RealityTunnel VPN.",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth.router)


# ── Exception Handlers ───────────────────────────────────────────────────────
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Validation error"},
    )


async def auth_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Authentication failed or token invalid"},
    )


async def duplicate_exception_handler(request: Request, exc: DuplicateEntityError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Duplicate entity"},
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unexpected service or database error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Unexpected service/database error"},
    )


app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

auth_exceptions = (
    AuthenticationServiceError,
    AccountNotActiveError,
    RefreshTokenNotFoundError,
    RefreshTokenExpiredError,
    RefreshTokenRevokedError,
    RefreshTokenReplayError,
    InvalidTokenError,
    TokenExpiredError,
    InvalidSignatureError,
    InvalidIssuerError,
    InvalidAudienceError,
    TokenNotYetValidError,
    EntityNotFoundError,
)
for exc_class in auth_exceptions:
    app.add_exception_handler(exc_class, auth_exception_handler)

app.add_exception_handler(DuplicateEntityError, duplicate_exception_handler)
app.add_exception_handler(ServiceError, general_exception_handler)
app.add_exception_handler(RepositoryError, general_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


@app.get("/", summary="Root", tags=["Meta"])
async def root():
    return {
        "service": "RealityTunnel Billing/Auth API",
        "version": settings.app_version,
        "phase": "1.3.5 — Authentication & Refresh API Endpoints",
        "docs": "/docs",
    }


@app.get("/version", summary="Version info", tags=["Meta"])
async def version():
    return {
        "version": settings.app_version,
        "environment": settings.environment,
    }
