"""
service.py — ProvisioningService orchestration layer.
Acts as the single gateway for all VPN user provisioning operations.
Enforces concurrency control (row locking), idempotency, and translates all provider exceptions into domain errors.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import advisory_xact_lock, AsyncSessionLocal
from app.exceptions import EntityNotFoundError, DatabaseOperationError, DuplicateEntityError
from app.models import ProvisioningProfile, ProvisioningState
from app.models.provisioning_retry import ProvisioningRetryItem, RetryItemStatus, ProvisioningAction
from app.repositories import AccountRepository, ProvisioningRepository, ProvisioningRetryRepository
from app.services.exceptions import (
    ProvisioningServiceError,
    ProvisioningProviderError,
    ProvisioningConflictError,
    ProvisioningUnavailableError,
    ProvisioningSynchronizationError,
    ProvisioningTimeoutError,
)
from app.services.provisioning.provider import ProvisioningProvider, ProvisionedUserDTO
from pydantic import BaseModel

class VpnIdentity(BaseModel):
    uuid: str
    username: str
    provider: str
    synced_at: datetime | None

logger = logging.getLogger(__name__)


class ProvisioningService:
    """
    Service for managing VPN user provisioning lifecycle.
    Decouples all HTTP routers and billing domain rules from Marzban or other VPN gateways.
    """

    def __init__(self, session: AsyncSession, provider: ProvisioningProvider, credential_service: Any | None = None) -> None:
        self.session = session
        self.provider = provider
        self.credential_service = credential_service
        self.account_repo = AccountRepository(session)
        self.provisioning_repo = ProvisioningRepository(session)
        self.retry_repo = ProvisioningRetryRepository(session)

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
        from sqlalchemy.exc import SQLAlchemyError
        if isinstance(exc, SQLAlchemyError):
            logger.exception("Database error during provisioning action=%s", action)
            return ProvisioningServiceError(f"Database error during {action}")

        logger.exception("Unhandled exception during provisioning action=%s", action)
        return ProvisioningServiceError(f"An unexpected error occurred during {action}")

    async def check_provider_health(self) -> bool:
        """Check health and readiness of the remote provisioning provider."""
        return await self.provider.health_check()

    async def _maybe_enqueue_retry(
        self,
        account_id: uuid.UUID,
        plan_id: str,
        expire_at: datetime | None,
        exc: Exception,
        action: ProvisioningAction = ProvisioningAction.PROVISION,
    ) -> None:
        """
        Check if an exception represents a transient failure (timeout, 500/502/503/504)
        and enqueue an item in the retry queue if not already pending.

        IMPORTANT: opens its own independent DB session rather than reusing self.session.
        This is deliberate — this method is always called after the caller's transaction
        has already been rolled back (or failed to commit). Reusing self.session would cause
        the enqueue to silently fail because the underlying connection is in an error state.
        An independent session guarantees the retry item is durably written even when the
        calling transaction is dead.
        """
        is_transient = False
        if isinstance(exc, (ProvisioningTimeoutError, ProvisioningUnavailableError)):
            is_transient = True
        elif isinstance(exc, ProvisioningProviderError):
            err_str = str(exc).lower()
            if any(code in err_str for code in ("500", "502", "503", "504", "timeout", "unreachable", "connection", "gateway")):
                is_transient = True

        if is_transient:
            try:
                now = datetime.now(timezone.utc)
                retry_item = ProvisioningRetryItem(
                    account_id=account_id,
                    plan_id=plan_id,
                    expires_at=expire_at or (now + timedelta(days=30)),
                    attempt_count=0,
                    next_retry_at=now + timedelta(seconds=30),
                    last_error=str(exc)[:499],
                    status=RetryItemStatus.PENDING,
                    action=action,
                )
                # Use a fresh session — caller's session may be in a broken/rolled-back state.
                async with AsyncSessionLocal() as enqueue_session:
                    enqueue_repo = ProvisioningRetryRepository(enqueue_session)
                    await enqueue_repo.create(retry_item, commit=True)
                logger.info("Enqueued transient provisioning failure for retry account_id=%s", account_id)
            except DuplicateEntityError:
                # Race recovery (Finding M-10): partial unique index
                # uq_provisioning_retry_one_pending_per_account rejects duplicate enqueues.
                logger.info(
                    "Provisioning retry already pending for account_id=%s; skipping duplicate enqueue",
                    account_id,
                )
            except Exception as e:
                logger.error("Failed to enqueue provisioning retry record: %s", str(e))

    async def provision_subscription(
        self,
        account_id: uuid.UUID,
        plan_id: str,
        expire_at: datetime | None = None,
        data_limit: int | None = None,
        *,
        commit: bool = True,
    ) -> ProvisioningProfile:
        """
        Provision or re-verify a VPN user profile for an account.
        Idempotent: calling twice will not duplicate users or throw errors if already provisioned.
        Acquires row-level exclusive lock on the provisioning profile.
        """
        try:
            await advisory_xact_lock(self.session, f"provisioning:{account_id}")
            account = await self.account_repo.get_by_id_or_raise(account_id)
            
            if plan_id == "free":
                raise ProvisioningConflictError("Free accounts cannot be provisioned.")
                
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
                if commit:
                    await self.session.commit()
                    await self.session.refresh(profile)
                else:
                    await self.session.flush()
                if self.credential_service:
                    await self.credential_service.generate(account_id)
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
                    vpn_uuid=user_dto.uuid,
                )
                self.session.add(profile)
            else:
                profile.remote_user_id = user_dto.remote_user_id
                profile.provisioning_state = ProvisioningState.ACTIVE
                profile.last_sync_at = now
                profile.last_error = None
                if user_dto.uuid:
                    profile.vpn_uuid = user_dto.uuid

            account.marzban_username = user_dto.remote_user_id
            if commit:
                await self.session.commit()
                await self.session.refresh(profile)
            else:
                await self.session.flush()
            if self.credential_service:
                await self.credential_service.generate(account_id)
            return profile

        except (DuplicateEntityError, IntegrityError):
            if commit:
                await self.session.rollback()
            logger.info("DuplicateEntityError caught during provision_subscription; returning existing profile for account_id=%s", account_id)
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=False)
            if profile:
                return profile
            raise ProvisioningConflictError("Duplicate entity exception but profile not found")
        except (EntityNotFoundError, DatabaseOperationError):
            raise
        except Exception as exc:
            if commit:
                await self.session.rollback()
            translated_exc = self._translate_exception(exc, "provision_subscription")
            await self._maybe_enqueue_retry(account_id, plan_id, expire_at, translated_exc, ProvisioningAction.PROVISION)
            raise translated_exc from exc

    async def extend_subscription(
        self,
        account_id: uuid.UUID,
        new_expires_at: datetime,
        *,
        commit: bool = True,
    ) -> ProvisioningProfile:
        """Extend expiration timestamp for an existing provisioned user."""
        try:
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=True)
            if not profile:
                raise ProvisioningConflictError(f"Cannot extend: no provisioning profile found for account {account_id}")

            if profile.provisioning_state == ProvisioningState.SUSPENDED and profile.suspension_reason in ("ADMIN", "FRAUD"):
                raise ProvisioningConflictError(
                    f"Profile {profile.id} is administratively suspended ({profile.suspension_reason}); "
                    "will not auto-reactivate via billing renewal. Requires explicit admin reactivation."
                )

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
            if commit:
                await self.session.commit()
                await self.session.refresh(profile)
            else:
                await self.session.flush()
            if self.credential_service:
                await self.credential_service.generate(account_id)
            return profile

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            if commit:
                await self.session.rollback()
            raise self._translate_exception(exc, "extend_subscription") from exc

    async def suspend_subscription(self, account_id: uuid.UUID, *, reason: str = "BILLING", commit: bool = True) -> ProvisioningProfile:
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
            profile.suspension_reason = reason
            profile.last_sync_at = datetime.now(timezone.utc)
            profile.last_error = None
            if commit:
                await self.session.commit()
                await self.session.refresh(profile)
            else:
                await self.session.flush()
            return profile

        except (EntityNotFoundError, DatabaseOperationError):
            raise
        except Exception as exc:
            if commit:
                await self.session.rollback()
            translated_exc = self._translate_exception(exc, "suspend_subscription")
            # Enqueue retry on transient failure
            await self._maybe_enqueue_retry(account_id, "unknown", None, translated_exc, ProvisioningAction.SUSPEND)
            raise translated_exc from exc

    async def reactivate_subscription(self, account_id: uuid.UUID, *, commit: bool = True) -> ProvisioningProfile:
        """Reactivate VPN access for a suspended account."""
        try:
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=True)
            if not profile:
                raise ProvisioningConflictError(f"Cannot reactivate: no provisioning profile found for account {account_id}")

            if profile.provisioning_state == ProvisioningState.SUSPENDED and profile.suspension_reason in ("ADMIN", "FRAUD"):
                raise ProvisioningConflictError(
                    f"Profile {profile.id} is administratively suspended ({profile.suspension_reason}); "
                    "will not auto-reactivate via billing renewal. Requires explicit admin reactivation."
                )

            try:
                await self.provider.unsuspend_user(profile.remote_user_id)
            except Exception as exc:
                profile.last_error = str(exc)
                await self.session.commit()
                raise

            profile.provisioning_state = ProvisioningState.ACTIVE
            profile.last_sync_at = datetime.now(timezone.utc)
            profile.last_error = None
            if commit:
                await self.session.commit()
                await self.session.refresh(profile)
            else:
                await self.session.flush()
            if self.credential_service:
                await self.credential_service.generate(account_id)
            return profile

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            if commit:
                await self.session.rollback()
            raise self._translate_exception(exc, "reactivate_subscription") from exc

    async def terminate_subscription(self, account_id: uuid.UUID, *, commit: bool = True) -> ProvisioningProfile | None:
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
            if commit:
                await self.session.commit()
                await self.session.refresh(profile)
            else:
                await self.session.flush()
            return profile

        except (EntityNotFoundError, DatabaseOperationError):
            raise
        except Exception as exc:
            if commit:
                await self.session.rollback()
            translated_exc = self._translate_exception(exc, "terminate_subscription")
            # Enqueue retry on transient failure
            await self._maybe_enqueue_retry(account_id, "unknown", None, translated_exc, ProvisioningAction.TERMINATE)
            raise translated_exc from exc

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
                
            if user_dto.uuid:
                profile.vpn_uuid = user_dto.uuid

            await self.session.commit()
            await self.session.refresh(profile)
            return profile

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            await self.session.rollback()
            raise self._translate_exception(exc, "synchronize") from exc

    async def get_provisioned_user(self, account_id: uuid.UUID) -> tuple[ProvisioningProfile, ProvisionedUserDTO]:
        """
        Retrieve canonical provisioning profile and latest remote user DTO (including links).
        """
        try:
            profile = await self.provisioning_repo.get_by_account_id(account_id)
            if not profile:
                raise EntityNotFoundError(f"Provisioning profile for account {account_id} not found.")

            try:
                user_dto = await self.provider.get_user(profile.remote_user_id)
            except Exception as exc:
                raise ProvisioningSynchronizationError(
                    f"Failed to fetch remote user '{profile.remote_user_id}': {str(exc)}"
                ) from exc

            if not user_dto:
                raise ProvisioningSynchronizationError(
                    f"Remote user '{profile.remote_user_id}' not found in provisioning provider."
                )

            return profile, user_dto

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            raise self._translate_exception(exc, "get_provisioned_user") from exc

    async def rotate_user_credentials(
        self, account_id: uuid.UUID, cutoff: datetime | None = None
    ) -> tuple[ProvisioningProfile, ProvisionedUserDTO]:
        """
        Atomically reset/rotate remote user credentials and update synchronization timestamp.
        Acquires row-level lock (SELECT ... FOR UPDATE) on the provisioning profile.
        """
        try:
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=True)
            if not profile:
                raise EntityNotFoundError(f"Provisioning profile for account {account_id} not found.")

            if cutoff and profile.last_sync_at and profile.last_sync_at > cutoff:
                logger.info("Skipping rotation for account_id=%s, already rotated.", account_id)
                # Re-fetch DTO to return since we skipped rotation
                user_dto = await self.provider.get_user(profile.remote_user_id)
                return profile, user_dto

            try:
                user_dto = await self.provider.reset_user_credentials(profile.remote_user_id)
            except Exception as exc:
                profile.last_error = str(exc)
                await self.session.commit()
                raise ProvisioningSynchronizationError(
                    f"Failed to reset credentials for remote user '{profile.remote_user_id}': {str(exc)}"
                ) from exc

            profile.last_sync_at = datetime.now(timezone.utc)
            profile.last_error = None

            if user_dto.status.lower() in ("disabled", "suspended", "inactive"):
                profile.provisioning_state = ProvisioningState.SUSPENDED
            elif user_dto.status.lower() == "active":
                profile.provisioning_state = ProvisioningState.ACTIVE
                
            if user_dto.uuid:
                profile.vpn_uuid = user_dto.uuid

            await self.session.commit()
            await self.session.refresh(profile)
            return profile, user_dto

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            await self.session.rollback()
            raise self._translate_exception(exc, "rotate_user_credentials") from exc

    async def get_vpn_identity(self, account_id: uuid.UUID, *, commit: bool = True) -> VpnIdentity:
        """
        Retrieve the cached VPN identity. If the UUID is missing (legacy user), 
        lazily synchronize from the provisioning provider, extract the UUID, 
        and save it to the cache.
        """
        try:
            profile = await self.provisioning_repo.get_by_account_id(account_id, for_update=True)
            if not profile:
                raise EntityNotFoundError(f"Provisioning profile for account {account_id} not found.")
                
            if not profile.vpn_uuid:
                try:
                    user_dto = await self.provider.get_user(profile.remote_user_id)
                except Exception as exc:
                    raise ProvisioningSynchronizationError(
                        f"Failed to fetch remote user '{profile.remote_user_id}': {str(exc)}"
                    ) from exc

                if not user_dto:
                    logger.warning(f"Remote user '{profile.remote_user_id}' not found, attempting to recreate...")
                    account = await AccountRepository.get_by_id(self.session, account_id)
                    if not account:
                        raise EntityNotFoundError(f"Account {account_id} not found.")
                    await self._create_user(self.session, profile, account)
                    user_dto = await self.provider.get_user(profile.remote_user_id)
                    if not user_dto:
                        raise ProvisioningSynchronizationError(f"Failed to fetch recreated identity for account {account_id}")
                    
                if not user_dto.uuid:
                    raise ProvisioningSynchronizationError(
                        f"Remote user '{profile.remote_user_id}' does not have a UUID (VLESS id missing)."
                    )
                    
                profile.vpn_uuid = user_dto.uuid
                profile.last_sync_at = datetime.now(timezone.utc)
                if commit:
                    await self.session.commit()
                    await self.session.refresh(profile)
                else:
                    await self.session.flush()

            return VpnIdentity(
                uuid=profile.vpn_uuid,
                username=profile.remote_user_id,
                provider="marzban",
                synced_at=profile.last_sync_at
            )

        except (EntityNotFoundError, DatabaseOperationError, ProvisioningServiceError):
            raise
        except Exception as exc:
            if commit:
                await self.session.rollback()
            raise self._translate_exception(exc, "get_vpn_identity") from exc

