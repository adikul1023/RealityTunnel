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
from app.routers import auth, devices, health
from app.services.exceptions import (
    AuthenticationServiceError,
    AccountNotActiveError,
    DeviceNotFoundError,
    DeviceOwnershipError,
    DeviceServiceError,
    InactiveDeviceError,
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
app.include_router(devices.router)


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


async def device_not_found_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Device not found"},
    )


async def device_inactive_exception_handler(request: Request, exc: InactiveDeviceError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Device is deactivated"},
    )


async def device_service_exception_handler(request: Request, exc: DeviceServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the exception type at ERROR level without the raw message (which may contain
    # internal database details). The full traceback is logged separately to allow
    # log aggregators to filter sensitive stack frames when needed.
    logger.error("Unexpected error: %s", type(exc).__name__, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Unexpected service/database error"},
    )


app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# auth_exceptions maps to auth_exception_handler (HTTP 401).
# All domain-level authentication and token validation exceptions are listed explicitly.
# RefreshTokenServiceError (base class) is included here so that database-level errors
# raised inside the refresh token service also produce 401 rather than falling through
# to the ServiceError → 500 handler by coincidence of exception hierarchy.
auth_exceptions = (
    AuthenticationServiceError,
    AccountNotActiveError,
    RefreshTokenServiceError,
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

app.add_exception_handler(DeviceNotFoundError, device_not_found_exception_handler)
app.add_exception_handler(DeviceOwnershipError, device_not_found_exception_handler)
app.add_exception_handler(InactiveDeviceError, device_inactive_exception_handler)
app.add_exception_handler(DeviceServiceError, device_service_exception_handler)
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
