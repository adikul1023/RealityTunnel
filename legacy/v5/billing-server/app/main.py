"""
RealityTunnel Billing/Auth Server
Phase 1.3.5 — Authentication & Refresh API Endpoints
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import engine, verify_db, AsyncSessionLocal
from app.exceptions import DuplicateEntityError, EntityNotFoundError, RepositoryError
from app.routers import auth, devices, health, admin_auth, admin, credentials, webhooks, billing, admin_billing, metrics, admin_recovery, client, account_2fa, admin_operations, agent, agent_bootstrap
from app.observability.middleware import RequestObservabilityMiddleware, record_exception_metric
from app.rate_limit import RateLimitMiddleware, RateLimitExceeded
from app.security_hardening import (
    SecurityHeadersMiddleware,
    InputValidationMiddleware,
    CSRFMiddleware,
    secret_rotation_service,
    audit_service,
    SecurityHardeningError,
    TLSValidationError,
    CSRFValidationError,
    InputValidationError,
    SecretRotationError,
)

from app.scheduler import JobScheduler




from app.services.exceptions import (
    AuthenticationServiceError,
    AccountNotActiveError,
    DeviceNotFoundError,
    DeviceOwnershipError,
    DeviceServiceError,
    InactiveDeviceError,
    DeviceLimitExceededError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenReplayError,
    RefreshTokenRevokedError,
    RefreshTokenServiceError,
    DeviceRevokedError,
    ServiceError,
    SubscriptionServiceError,
    TokenExpiredError,
    TokenNotYetValidError,
    UnknownPlanError,
    AdminSecurityError,
    AdminNotActiveError,
    InvalidAdminTokenError,
    AdminTokenExpiredError,
    PaymentNotFoundError,
    MFANotImplementedYet,
)

from app.logging_config import configure_logging
configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup / shutdown lifecycle."""
    logger.info("Billing server starting up…")
    from app.core.startup_validator import validate_startup_configuration
    validate_startup_configuration(settings)
    logger.info("Database URL: %s", settings.database_url_safe)
    scheduler = JobScheduler(AsyncSessionLocal)
    scheduler.start()
    app.state.scheduler = scheduler
    app.state.secret_rotation = secret_rotation_service
    app.state.audit = audit_service
    from app.performance.cache import get_cache
    from app.performance.profiler import profiler
    app.state.cache = get_cache()
    app.state.profiler = profiler
    yield
    logger.info("Billing server shutting down…")
    await scheduler.stop()
    await engine.dispose()



app = FastAPI(
    title="RealityTunnel Billing/Auth API",
    description="Billing & authentication backend for RealityTunnel VPN.",
    version=settings.app_version,
    docs_url=settings.docs_url_effective,       # M-7: None in production
    redoc_url=settings.redoc_url_effective,     # M-7: None in production
    openapi_url=settings.openapi_url_effective, # M-7: None in production
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(client.router)
app.include_router(devices.router)
app.include_router(admin_auth.router)
app.include_router(admin.router)
app.include_router(credentials.router)
app.include_router(webhooks.router)
app.include_router(billing.router)
app.include_router(admin_billing.router)
app.include_router(metrics.router)
app.include_router(admin_recovery.router)
app.include_router(account_2fa.router)
app.include_router(admin_operations.router)
app.include_router(agent.router)
app.include_router(agent_bootstrap.router)

app.add_middleware(CSRFMiddleware)
app.add_middleware(InputValidationMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestObservabilityMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)






# ── Exception Handlers ───────────────────────────────────────────────────────
def _record_exc(request: Request, exc: Exception, status_code: int) -> None:
    record_exception_metric(exc, request, status_code)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    _record_exc(request, exc, exc.status_code)
    content = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
    return JSONResponse(status_code=exc.status_code, content=content)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_400_BAD_REQUEST)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Validation error", "code": "VALIDATION_ERROR"},
    )


async def auth_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_401_UNAUTHORIZED)
    from app.services.exceptions import RefreshTokenReplayError, AccountNotActiveError
    code = getattr(exc, "code", None)
    if not code:
        if isinstance(exc, RefreshTokenReplayError):
            code = "REPLAY_DETECTED"
        elif isinstance(exc, AccountNotActiveError):
            code = "ACCOUNT_DISABLED"
        else:
            code = "AUTH_ERROR"
    detail_msg = getattr(exc, "detail", None)
    if not detail_msg or not isinstance(detail_msg, str):
        detail_msg = str(exc) if str(exc) else "Authentication failed or token invalid"
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": detail_msg, "code": code},
    )


async def duplicate_exception_handler(request: Request, exc: DuplicateEntityError) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_409_CONFLICT)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Duplicate entity", "code": "DUPLICATE_ENTITY"},
    )


async def device_not_found_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_404_NOT_FOUND)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Device not found", "code": "DEVICE_NOT_FOUND"},
    )


async def payment_not_found_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_404_NOT_FOUND)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Payment not found", "code": "PAYMENT_NOT_FOUND"},
    )



async def device_inactive_exception_handler(request: Request, exc: InactiveDeviceError) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_400_BAD_REQUEST)
    content = getattr(exc, "detail", None) if isinstance(getattr(exc, "detail", None), dict) else {"detail": "Device is deactivated", "code": "DEVICE_DEACTIVATED"}
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=content,
    )


async def device_limit_exceeded_exception_handler(request: Request, exc: DeviceLimitExceededError) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_403_FORBIDDEN)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=exc.detail,
    )


async def unknown_plan_exception_handler(request: Request, exc: UnknownPlanError) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_400_BAD_REQUEST)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def device_service_exception_handler(request: Request, exc: DeviceServiceError) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_400_BAD_REQUEST)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_500_INTERNAL_SERVER_ERROR)
    # Log the exception type at ERROR level without the raw message (which may contain
    # internal database details). The full traceback is logged separately to allow
    # log aggregators to filter sensitive stack frames when needed.
    logger.error("Unexpected error: %s", type(exc).__name__, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Unexpected service/database error"},
    )


async def mfa_not_implemented_exception_handler(request: Request, exc: MFANotImplementedYet) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_501_NOT_IMPLEMENTED)
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": "MFA for administrative accounts is not yet implemented."},
    )



async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    _record_exc(request, exc, status.HTTP_429_TOO_MANY_REQUESTS)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded", "retry_after": exc.retry_after},
        headers=getattr(exc, "headers", None),
    )



app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
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
    DeviceRevokedError,
    InvalidTokenError,
    TokenExpiredError,
    InvalidSignatureError,
    InvalidIssuerError,
    InvalidAudienceError,
    TokenNotYetValidError,
    EntityNotFoundError,
    AdminNotActiveError,
    InvalidAdminTokenError,
    AdminTokenExpiredError,
    AdminSecurityError,
)
for exc_class in auth_exceptions:
    app.add_exception_handler(exc_class, auth_exception_handler)

app.add_exception_handler(MFANotImplementedYet, mfa_not_implemented_exception_handler)
app.add_exception_handler(DeviceNotFoundError, device_not_found_exception_handler)
app.add_exception_handler(DeviceOwnershipError, device_not_found_exception_handler)
app.add_exception_handler(PaymentNotFoundError, payment_not_found_exception_handler)
app.add_exception_handler(InactiveDeviceError, device_inactive_exception_handler)

app.add_exception_handler(DeviceLimitExceededError, device_limit_exceeded_exception_handler)
app.add_exception_handler(DeviceServiceError, device_service_exception_handler)
app.add_exception_handler(UnknownPlanError, unknown_plan_exception_handler)
app.add_exception_handler(SubscriptionServiceError, device_service_exception_handler)
app.add_exception_handler(DuplicateEntityError, duplicate_exception_handler)
async def security_hardening_exception_handler(request: Request, exc: SecurityHardeningError) -> JSONResponse:
    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, CSRFValidationError):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, InputValidationError) and "exceeds maximum" in getattr(exc, "message", str(exc)):
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    _record_exc(request, exc, status_code)
    return JSONResponse(
        status_code=status_code,
        content={"detail": getattr(exc, "message", str(exc)), "error_type": type(exc).__name__},
    )


app.add_exception_handler(SecurityHardeningError, security_hardening_exception_handler)
app.add_exception_handler(TLSValidationError, security_hardening_exception_handler)
app.add_exception_handler(CSRFValidationError, security_hardening_exception_handler)
app.add_exception_handler(InputValidationError, security_hardening_exception_handler)
app.add_exception_handler(SecretRotationError, security_hardening_exception_handler)
app.add_exception_handler(ServiceError, general_exception_handler)
app.add_exception_handler(RepositoryError, general_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


@app.get("/", summary="Root", tags=["Meta"])
async def root():
    return {
        "service": "RealityTunnel Billing/Auth API",
        "version": settings.app_version,
        "phase": "3.2 — Observability & Monitoring",
        "docs": "/docs",
    }




@app.get("/version", summary="Version info", tags=["Meta"])
async def version():
    return {
        "version": settings.app_version,
        "environment": settings.environment,
    }
