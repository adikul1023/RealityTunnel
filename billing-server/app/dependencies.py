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
    AdminUserRepository,
)
from app.config import settings
from app.security.jwt_service import JWTService
from app.security.admin_password import AdminPasswordService
from app.security.admin_jwt import AdminJWTService
from app.services import (
    AuthenticationService,
    DeviceService,
    RefreshTokenService,
    ConnectionSignalService,
    AdminAuthenticationService,
    AdminAccountService,
    MarzbanProvisioningProvider,
    ProvisioningService,
    CredentialService,
    SubscriptionService,
    PaymentService,
    WebhookService,
    SubscriptionPlanService,
    BillingService,
    RazorpayProvider,
)
from app.models.admin_user import AdminUser


logger = logging.getLogger(__name__)

# Bearer authentication schemes for OpenAPI Swagger documentation
customer_oauth2_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="CustomerBearer",
    description="Customer Ed25519 Access JWT",
)
oauth2_scheme = customer_oauth2_scheme  # backward compatibility alias

admin_oauth2_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="AdminBearer",
    description="Administrative Ed25519 Access JWT",
)

# Singleton JWT service instance (stateless Ed25519 signer/verifier)
# Instantiated once on first request; loads keys from disk once and never regenerates.
_jwt_service: JWTService | None = None
_admin_password_service: AdminPasswordService | None = None
_admin_jwt_service: AdminJWTService | None = None


def get_jwt_service() -> JWTService:
    """Dependency provider yielding the stateless singleton JWTService."""
    global _jwt_service
    if _jwt_service is None:
        _jwt_service = JWTService()
    return _jwt_service


def get_admin_password_service() -> AdminPasswordService:
    """Dependency provider yielding the stateless singleton AdminPasswordService."""
    global _admin_password_service
    if _admin_password_service is None:
        _admin_password_service = AdminPasswordService()
    return _admin_password_service


def get_admin_jwt_service() -> AdminJWTService:
    """Dependency provider yielding the stateless singleton AdminJWTService."""
    global _admin_jwt_service
    if _admin_jwt_service is None:
        _admin_jwt_service = AdminJWTService()
    return _admin_jwt_service


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


async def get_admin_repo(session: AsyncSession = Depends(get_db)) -> AdminUserRepository:
    """Dependency provider yielding AdminUserRepository tied to the request session."""
    return AdminUserRepository(session)


async def get_admin_auth_service(
    admin_repo: AdminUserRepository = Depends(get_admin_repo),
    password_service: AdminPasswordService = Depends(get_admin_password_service),
    jwt_service: AdminJWTService = Depends(get_admin_jwt_service),
) -> AdminAuthenticationService:
    """Dependency provider yielding AdminAuthenticationService."""
    return AdminAuthenticationService(admin_repo, password_service, jwt_service)


async def get_current_admin(
    request: Request,
    _bearer: HTTPAuthorizationCredentials | None = Depends(admin_oauth2_scheme),
    admin_auth_service: AdminAuthenticationService = Depends(get_admin_auth_service),
    admin_jwt_service: AdminJWTService = Depends(get_admin_jwt_service),
) -> AdminUser:
    """
    Dependency yielding the authenticated and validated AdminUser model from an HTTP Authorization Bearer token.
    Strictly isolated from customer account authentication.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.info("Admin authentication failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or token invalid",
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        logger.info("Admin authentication failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or token invalid",
        )

    token = parts[1].strip()
    if not token:
        logger.info("Admin authentication failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or token invalid",
        )

    try:
        claims = admin_jwt_service.verify_admin_token(token)
    except Exception:
        logger.info("Admin token invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or token invalid",
        )

    try:
        admin = await admin_auth_service.get_active_admin_by_id(uuid.UUID(claims.sub))
    except Exception:
        logger.info("Admin authentication failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed or token invalid",
        )

    logger.info("Admin authentication succeeded")
    return admin


async def get_admin_account_service(
    account_repo: AccountRepository = Depends(get_account_repo),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_repo),
) -> AdminAccountService:
    """Dependency provider yielding AdminAccountService for administrative account management."""
    return AdminAccountService(account_repo, refresh_repo)


async def require_super_admin(
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUser:
    """
    FastAPI dependency that enforces super-admin privilege.
    Raises HTTP 403 Forbidden if the authenticated admin is not a super-admin.
    Read-only operations use get_current_admin(); write operations use require_super_admin().
    """
    if not admin.is_super_admin:
        logger.info("Admin access denied: super-admin privilege required")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admin privilege required for this operation",
        )
    return admin


_marzban_provider: MarzbanProvisioningProvider | None = None


def get_marzban_provider() -> MarzbanProvisioningProvider:
    """Yield singleton Marzban provisioning provider configured with app settings."""
    global _marzban_provider
    if _marzban_provider is None:
        _marzban_provider = MarzbanProvisioningProvider()
    return _marzban_provider


async def get_provisioning_service(
    session: AsyncSession = Depends(get_db),
    provider: MarzbanProvisioningProvider = Depends(get_marzban_provider),
) -> ProvisioningService:
    """Yield ProvisioningService instance wired to current database session, Marzban provider, and CredentialService."""
    prov_svc = ProvisioningService(session, provider)
    cred_svc = CredentialService(session, prov_svc)
    prov_svc.credential_service = cred_svc
    return prov_svc


async def get_credential_service(
    session: AsyncSession = Depends(get_db),
    provisioning_service: ProvisioningService = Depends(get_provisioning_service),
) -> CredentialService:
    """Yield CredentialService instance for VPN credential lifecycle and config generation."""
    if provisioning_service.credential_service:
        return provisioning_service.credential_service
    return CredentialService(session, provisioning_service)


async def get_subscription_service(
    session: AsyncSession = Depends(get_db),
    provisioning_service: ProvisioningService = Depends(get_provisioning_service),
) -> SubscriptionService:
    """Yield SubscriptionService wired to current database session and ProvisioningService."""
    return SubscriptionService(session, provisioning_service=provisioning_service)


_razorpay_provider: RazorpayProvider | None = None


def get_razorpay_provider() -> RazorpayProvider:
    """Yield singleton Razorpay payment provider."""
    global _razorpay_provider
    if _razorpay_provider is None:
        _razorpay_provider = RazorpayProvider(settings)
    return _razorpay_provider



async def get_payment_service(
    session: AsyncSession = Depends(get_db),
    provider: RazorpayProvider = Depends(get_razorpay_provider),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
) -> PaymentService:
    """Yield PaymentService wired to current session, gateway provider, and SubscriptionService."""
    return PaymentService(session, provider, subscription_service=subscription_service)


async def get_webhook_service(
    payment_service: PaymentService = Depends(get_payment_service),
) -> WebhookService:
    """Yield WebhookService wired to PaymentService."""
    return WebhookService(payment_service)


def get_plan_service() -> SubscriptionPlanService:
    """Yield SubscriptionPlanService."""
    return SubscriptionPlanService()


async def get_billing_service(
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    payment_service: PaymentService = Depends(get_payment_service),
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
) -> BillingService:
    """Yield BillingService wired to SubscriptionService, PaymentService, and SubscriptionPlanService."""
    return BillingService(subscription_service, payment_service, plan_service)



