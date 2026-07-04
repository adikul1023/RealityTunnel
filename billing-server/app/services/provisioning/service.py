"""
service.py — ProvisioningService orchestration layer.
Acts as the single gateway for all VPN user provisioning operations.
Enforces concurrency control (row locking), idempotency, and translates all provider exceptions into domain errors.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EntityNotFoundError, DatabaseOperationError
from app.models import ProvisioningProfile, ProvisioningState
from app.repositories import AccountRepository, ProvisioningRepository
from app.services.exceptions import (
    ProvisioningServiceError,
    ProvisioningProviderError,
    ProvisioningConflictError,
    ProvisioningUnavailableError,
    ProvisioningSynchronizationError,
    ProvisioningTimeoutError,
)
from app.services.provisioning.provider import ProvisioningProvider

logger = logging.getLogger(__name__)


class ProvisioningService:
    """
    Service for managing VPN user provisioning lifecycle.
    Decouples all HTTP routers and billing domain rules from Marzban or other VPN gateways.
    """

    def __init__(self, session: AsyncSession, provider: ProvisioningProvider) -> None:
        self.session = session
        self.provider = provider
        self.account_repo = AccountRepository(session)
        self.provisioning_repo = ProvisioningRepository(session)

    def _translate_exception(self, exc: Exception, action: str) -> ProvisioningServiceError:
        """Ensure no external or HTTP exceptions leak out of ProvisioningService."""
        if isinstance(
            exc,
            (
                ProvisioningServiceError,
                ProvisioningProviderError,
                ProvisioningConflictError,
                ProvisioningUnavailableError,
                ProvisioningSynchronizationError,
                ProvisioningTimeoutError,
            ),
        ):
            return exc
        logger.error("Unhandled exception during provisioning action=%s: %s", action, str(exc))
        return ProvisioningServiceError(f"Provisioning error during {action}: {str(exc)}")

    async def provision_subscription(
        self,
        account_id: uuid.UUID,
        plan_id: str,
        expire_at: datetime | None = None,
        data_limit: int | None = None,
    ) -> ProvisioningProfile:
        """
        Provision or re-verify a VPN user profile for an account.
        Idempotent: calling twice will not duplicate users or throw errors if already provisioned.
        Acquires row-level exclusive lock on the provisioning profile.
        """
        try:
            account = await self.account_repo.get_by_id_or_raise(account_id)
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=True)

            expire_ts = int(expire_at.timestamp()) if expire_at else None

            if profile and profile.provisioning_state == ProvisioningState.ACTIVE:
                logger.info(
                    "Account already has an active provisioning profile account_id=%s remote_user_id=%s",
                    account_id,
                    profile.remote_user_id,
                )
                try:
                    await self.provider.get_user(profile.remote_user_id)
                except Exception as exc:
                    logger.warning("Remote user check failed during idempotent provision: %s", str(exc))
                profile.last_sync_at = datetime.now(timezone.utc)
                profile.last_error = None
                await self.session.commit()
                await self.session.refresh(profile)
                return profile

            remote_username = account.marzban_username or f"user_{account.account_id.lower()}"

            try:
                user_dto = await self.provider.create_user(
                    username=remote_username,
                    data_limit=data_limit,
                    expire_at=expire_ts,
                )
            except ProvisioningConflictError:
                logger.info("Remote user already existed in provider username=%s, updating instead", remote_username)
                user_dto = await self.provider.update_user(
                    username=remote_username,
                    data_limit=data_limit,
                    expire_at=expire_ts,
                    status="active",
                )

            now = datetime.now(timezone.utc)
            if not profile:
                profile = ProvisioningProfile(
                    account_id=account_id,
                    remote_user_id=user_dto.remote_user_id,
                    provisioning_state=ProvisioningState.ACTIVE,
                    last_sync_at=now,
                    last_error=None,
                )
                self.session.add(profile)
            else:
                profile.remote_user_id = user_dto.remote_user_id
                profile.provisioning_state = ProvisioningState.ACTIVE
                profile.last_sync_at = now
                profile.last_error = None

            account.marzban_username = user_dto.remote_user_id
            await self.session.commit()
            await self.session.refresh(profile)
            return profile

        except (EntityNotFoundError, DatabaseOperationError):
            raise
        except Exception as exc:
            await self.session.rollback()
            raise self._translate_exception(exc, "provision_subscription") from exc

    async def extend_subscription(
        self,
        account_id: uuid.UUID,
        new_expires_at: datetime,
    ) -> ProvisioningProfile:
        """Extend expiration timestamp for an existing provisioned user."""
        try:
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=True)
            if not profile:
                raise ProvisioningConflictError(f"Cannot extend: no provisioning profile found for account {account_id}")

            expire_ts = int(new_expires_at.timestamp())
            try:
                await self.provider.update_user(profile.remote_user_id, expire_at=expire_ts, status="active")
            except Exception as exc:
                profile.last_error = str(exc)
                await self.session.commit()
                raise

            profile.provisioning_state = ProvisioningState.ACTIVE
            profile.last_sync_at = datetime.now(timezone.utc)
            profile.last_error = None
            await self.session.commit()
            await self.session.refresh(profile)
            return profile

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            await self.session.rollback()
            raise self._translate_exception(exc, "extend_subscription") from exc

    async def suspend_subscription(self, account_id: uuid.UUID) -> ProvisioningProfile:
        """
        Suspend VPN access for an account.
        Idempotent: calling twice on an already suspended profile succeeds without error.
        """
        try:
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=True)
            if not profile:
                raise ProvisioningConflictError(f"Cannot suspend: no provisioning profile found for account {account_id}")

            if profile.provisioning_state == ProvisioningState.SUSPENDED:
                logger.info("Profile already suspended for account_id=%s", account_id)
                return profile

            try:
                await self.provider.suspend_user(profile.remote_user_id)
            except Exception as exc:
                profile.last_error = str(exc)
                await self.session.commit()
                raise

            profile.provisioning_state = ProvisioningState.SUSPENDED
            profile.last_sync_at = datetime.now(timezone.utc)
            profile.last_error = None
            await self.session.commit()
            await self.session.refresh(profile)
            return profile

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            await self.session.rollback()
            raise self._translate_exception(exc, "suspend_subscription") from exc

    async def reactivate_subscription(self, account_id: uuid.UUID) -> ProvisioningProfile:
        """Reactivate VPN access for a suspended account."""
        try:
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=True)
            if not profile:
                raise ProvisioningConflictError(f"Cannot reactivate: no provisioning profile found for account {account_id}")

            try:
                await self.provider.unsuspend_user(profile.remote_user_id)
            except Exception as exc:
                profile.last_error = str(exc)
                await self.session.commit()
                raise

            profile.provisioning_state = ProvisioningState.ACTIVE
            profile.last_sync_at = datetime.now(timezone.utc)
            profile.last_error = None
            await self.session.commit()
            await self.session.refresh(profile)
            return profile

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            await self.session.rollback()
            raise self._translate_exception(exc, "reactivate_subscription") from exc

    async def terminate_subscription(self, account_id: uuid.UUID) -> ProvisioningProfile | None:
        """
        Permanently delete the remote VPN user for an account.
        Idempotent: calling twice succeeds without error.
        """
        try:
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=True)
            if not profile:
                logger.info("No provisioning profile found to terminate for account_id=%s", account_id)
                return None

            if profile.provisioning_state == ProvisioningState.TERMINATED:
                logger.info("Profile already terminated for account_id=%s", account_id)
                return profile

            try:
                await self.provider.delete_user(profile.remote_user_id)
            except Exception as exc:
                profile.last_error = str(exc)
                await self.session.commit()
                raise

            profile.provisioning_state = ProvisioningState.TERMINATED
            profile.last_sync_at = datetime.now(timezone.utc)
            profile.last_error = None
            await self.session.commit()
            await self.session.refresh(profile)
            return profile

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            await self.session.rollback()
            raise self._translate_exception(exc, "terminate_subscription") from exc

    async def synchronize(self, account_id: uuid.UUID) -> ProvisioningProfile:
        """
        Synchronize local provisioning profile with remote provider state.
        Translates provider status into local enum and clears or records diagnostics.
        """
        try:
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=True)
            if not profile:
                raise ProvisioningSynchronizationError(
                    f"Cannot synchronize: no provisioning profile found for account {account_id}"
                )

            try:
                user_dto = await self.provider.sync_user(profile.remote_user_id)
            except Exception as exc:
                profile.last_error = str(exc)
                await self.session.commit()
                raise ProvisioningSynchronizationError(f"Sync failed for remote user {profile.remote_user_id}: {str(exc)}") from exc

            profile.last_sync_at = datetime.now(timezone.utc)
            profile.last_error = None

            if user_dto.status.lower() in ("disabled", "suspended", "inactive"):
                profile.provisioning_state = ProvisioningState.SUSPENDED
            elif user_dto.status.lower() == "active":
                profile.provisioning_state = ProvisioningState.ACTIVE

            await self.session.commit()
            await self.session.refresh(profile)
            return profile

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            await self.session.rollback()
            raise self._translate_exception(exc, "synchronize") from exc
