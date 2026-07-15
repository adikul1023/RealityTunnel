"""
admin_account.py — Administrative Account Management Service.

Pure domain service providing account listing, status management, subscription extension,
and session revocation for administrative operations.

ARCHITECTURAL INVARIANTS:
1. Only AccountRepository and RefreshTokenRepository are used. No direct session access.
2. No business logic is duplicated from AuthenticationService or RefreshTokenService.
3. Never logs Account IDs, hashes, or tokens. Logs only generic event descriptions.
4. Raises AdminAccountNotFoundError (domain exception) when an account_id is unknown.
   The router translates this to HTTP 404.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.exceptions import RepositoryError
from app.models.account import Account
from app.models.base import SubscriptionStatus, SubscriptionLifecycleStatus
from app.models.subscription import Subscription
from app.models.subscription_plan import PLANS_REGISTRY
from app.repositories.account_repository import AccountRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.provisioning.service import ProvisioningService, ProvisioningState
from app.security_hardening.audit import audit_service
from app.services.exceptions import (
    AdminAccountNotFoundError,
    AdminServiceError,
)

logger = logging.getLogger(__name__)


class AdminAccountService:
    """
    Domain service for administrative account management.
    Orchestrates account queries, status mutations, and session revocation.
    Strictly independent of HTTP layer and customer-facing authentication.
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        refresh_repo: RefreshTokenRepository,
        subscription_repo: SubscriptionRepository | None = None,
        provisioning_service: ProvisioningService | None = None,
    ) -> None:
        self.account_repo = account_repo
        self.refresh_repo = refresh_repo
        self.subscription_repo = subscription_repo
        self.provisioning_service = provisioning_service

    # ── Private helpers ─────────────────────────────────────────────────────

    async def _get_by_account_id(
        self, account_id_str: str, *, for_update: bool = False
    ) -> Account:
        """
        Internal lookup by human-readable account_id string.
        Raises AdminAccountNotFoundError if not found, AdminServiceError on DB failure.
        If for_update=True, acquires a row-level exclusive lock so the caller's subsequent
        read-modify-write of this account happens atomically within a single transaction
        (Finding H-4: prevents lost-update races under concurrent admin mutations).
        """
        try:
            account = await self.account_repo.get_by_account_id(
                account_id_str, for_update=for_update
            )
        except RepositoryError as exc:
            logger.error("Repository error during admin account lookup")
            raise AdminServiceError(
                "Database error during administrative account lookup"
            ) from exc

        if account is None:
            raise AdminAccountNotFoundError(f"Account not found")

        return account

    # ── Queries ──────────────────────────────────────────────────────────────

    async def list_accounts(self, *, limit: int = 50, offset: int = 0) -> list[Account]:
        """
        Return a paginated list of accounts ordered by most recently created first.
        """
        try:
            return await self.account_repo.list_all(limit=limit, offset=offset)
        except RepositoryError as exc:
            logger.error("Repository error listing accounts")
            raise AdminServiceError("Database error listing accounts") from exc

    async def get_account(self, account_id_str: str) -> Account:
        """
        Retrieve an account by its human-readable account_id string.
        Raises AdminAccountNotFoundError if the account does not exist.
        """
        return await self._get_by_account_id(account_id_str)

    # ── Mutations ────────────────────────────────────────────────────────────

    async def suspend_account(self, account_id_str: str) -> Account:
        """
        Set account status to SUSPENDED.
        Idempotent: suspending an already suspended account is a no-op.
        """
        account = await self._get_by_account_id(account_id_str, for_update=True)
        try:
            account = await self.account_repo.update(
                account, status=SubscriptionStatus.SUSPENDED
            )
        except RepositoryError as exc:
            logger.error("Repository error suspending account")
            raise AdminServiceError("Database error suspending account") from exc
        logger.info("Administrative account suspension completed.")
        return account

    async def activate_account(self, account_id_str: str) -> Account:
        """
        Set account status to ACTIVE.
        Idempotent: activating an already active account is a no-op.
        """
        account = await self._get_by_account_id(account_id_str, for_update=True)
        try:
            account = await self.account_repo.update(
                account, status=SubscriptionStatus.ACTIVE
            )
        except RepositoryError as exc:
            logger.error("Repository error activating account")
            raise AdminServiceError("Database error activating account") from exc
        logger.info("Administrative account activation completed.")
        return account

    async def extend_subscription(self, account_id_str: str, days: int) -> Account:
        """
        Extend (or set) subscription_expires_at by the given number of days from now.
        If the account already has a future expiry, extends from that date.
        Sets status to ACTIVE if currently EXPIRED.
        """
        if days < 1 or days > 3650:
            raise AdminServiceError("Extension days must be between 1 and 3650")

        # Finding H-4: lock the row before reading subscription_expires_at so the
        # read-modify-write below is atomic. Without this, two concurrent extensions can
        # both read the same stale base expiry and one extension is silently lost.
        account = await self._get_by_account_id(account_id_str, for_update=True)

        now = datetime.now(timezone.utc)
        current_expiry = account.subscription_expires_at
        if current_expiry is not None:
            if current_expiry.tzinfo is None:
                current_expiry = current_expiry.replace(tzinfo=timezone.utc)
            base = max(current_expiry, now)
        else:
            base = now

        new_expiry = base + timedelta(days=days)

        updates: dict = {"subscription_expires_at": new_expiry}
        if account.status == SubscriptionStatus.EXPIRED:
            updates["status"] = SubscriptionStatus.ACTIVE

        try:
            account = await self.account_repo.update(account, **updates)
        except RepositoryError as exc:
            logger.error("Repository error extending subscription")
            raise AdminServiceError("Database error extending subscription") from exc

        logger.info("Administrative subscription extension completed.")
        return account

    async def grant_subscription(
        self,
        account_id_str: str,
        plan_id: str,
        duration_days: int,
        data_quota_gb: int | None = None,
        device_limit: int | None = None,
        payment_method: str | None = None,
        payment_reference: str | None = None,
        notes: str | None = None,
        admin_id: uuid.UUID | None = None,
    ) -> Account:
        """
        Atomic operator-driven beta onboarding grant.
        Updates account, creates/updates subscription, provisions Marzban, records audit trail.
        """
        if not self.subscription_repo or not self.provisioning_service:
            raise AdminServiceError("Service misconfigured: Missing subscription/provisioning dependencies.")

        clean_plan_id = plan_id.strip().lower()
        plan = PLANS_REGISTRY.get(clean_plan_id)
        if not plan:
            raise AdminServiceError(f"Unknown subscription plan ID: '{clean_plan_id}'")

        if duration_days < 1 or duration_days > 3650:
            raise AdminServiceError("Duration days must be between 1 and 3650")

        # Determine limits
        data_limit = (data_quota_gb * 1024**3) if data_quota_gb and data_quota_gb > 0 else plan.data_quota_bytes

        # 1. Lock Account
        account = await self._get_by_account_id(account_id_str, for_update=True)
        now = datetime.now(timezone.utc)
        new_expiry = now + timedelta(days=duration_days)
        expire_ts = int(new_expiry.timestamp())

        try:
            # 2. Update Account (Uncommitted)
            account = await self.account_repo.update(
                account,
                plan_id=plan.plan_id,
                status=SubscriptionStatus.ACTIVE,
                subscription_expires_at=new_expiry,
                commit=False,
            )

            # 3. Create or update Subscription (Uncommitted)
            active_sub = await self.subscription_repo.get_active_for_account(account.id, now, for_update=True)
            if active_sub:
                await self.subscription_repo.update(
                    active_sub,
                    plan_id=plan.plan_id,
                    status=SubscriptionLifecycleStatus.ACTIVE,
                    expires_at=new_expiry,
                    commit=False,
                )
            else:
                await self.subscription_repo.create(
                    account_id=account.id,
                    plan_id=plan.plan_id,
                    status=SubscriptionLifecycleStatus.ACTIVE,
                    starts_at=now,
                    expires_at=new_expiry,
                    commit=False,
                )

            # 4. Sync Marzban Provisioning (DB only initially)
            profile = await self.provisioning_service.provisioning_repo.get_by_account_id(account.id, for_update=True)
            
            if not profile:
                remote_username = account.marzban_username or f"user_{account.account_id.lower()}"
                profile = ProvisioningProfile(
                    account_id=account.id,
                    remote_user_id=remote_username,
                    provisioning_state=ProvisioningState.ACTIVE if account.marzban_username else ProvisioningState.PENDING,
                    last_sync_at=None,
                    last_error=None,
                )
                self.provisioning_service.session.add(profile)
                account.marzban_username = remote_username
            else:
                profile.provisioning_state = ProvisioningState.ACTIVE
                profile.last_error = None
            
            if self.provisioning_service.credential_service:
                await self.provisioning_service.credential_service.generate(account.id)

            # 5. Record Audit Event
            await audit_service.record_event(
                event_type="subscription_change",
                actor_id=str(admin_id) if admin_id else "SYSTEM",
                target_id=str(account.id),
                details={
                    "action": "grant_subscription",
                    "account_id_str": account.account_id,
                    "previous_plan": "none", # Cannot easily query previous here unless tracked
                    "new_plan": plan.plan_id,
                    "previous_expiry": None,
                    "new_expiry": new_expiry.isoformat(),
                    "operator_id": str(admin_id) if admin_id else "SYSTEM",
                    "duration_days": duration_days,
                    "payment_method": payment_method,
                    "payment_reference": payment_reference,
                    "notes": notes,
                },
            )

            # 6. Commit atomic transaction
            await self.account_repo.session.commit()
            await self.account_repo.session.refresh(account)
            
            # 7. Post-Commit Sync (Swallow exceptions, leave profile in appropriate state if failed)
            sync_status = "success"
            try:
                if profile.provisioning_state == ProvisioningState.PENDING:
                    # New user
                    user_dto = await self.provisioning_service.provider.create_user(
                        username=profile.remote_user_id,
                        data_limit=data_limit,
                        expire_at=expire_ts,
                    )
                    # We need a separate short transaction to update the UUID and state
                    async with self.account_repo.session.begin_nested() if self.account_repo.session.in_transaction() else self.account_repo.session.begin():
                        profile.vpn_uuid = user_dto.uuid
                        profile.provisioning_state = ProvisioningState.ACTIVE
                        profile.last_sync_at = datetime.now(timezone.utc)
                        await self.account_repo.session.commit()
                else:
                    # Existing user update
                    await self.provisioning_service.provider.update_user(
                        username=profile.remote_user_id,
                        data_limit=data_limit,
                        expire_at=expire_ts,
                        status="active"
                    )
                    async with self.account_repo.session.begin_nested() if self.account_repo.session.in_transaction() else self.account_repo.session.begin():
                        profile.provisioning_state = ProvisioningState.ACTIVE
                        profile.last_sync_at = datetime.now(timezone.utc)
                        await self.account_repo.session.commit()
            except Exception as exc:
                logger.error("Failed to sync Marzban user %s post-commit: %s", profile.remote_user_id, exc)
                sync_status = "queued_for_retry"
                # Record the error in a separate short transaction and mark as FAILED/NEEDS_SYNC
                async with self.account_repo.session.begin_nested() if self.account_repo.session.in_transaction() else self.account_repo.session.begin():
                    profile = await self.provisioning_service.provisioning_repo.get_by_account_id(account.id, for_update=True)
                    if profile:
                        profile.last_error = str(exc)
                        # We use PENDING to signal needs_sync since it's the closest equivalent
                        if profile.provisioning_state != ProvisioningState.ACTIVE:
                            profile.provisioning_state = ProvisioningState.PENDING 
                    await self.account_repo.session.commit()
                # We can call the explicit retry logic from provisioning_service
                translated_exc = self.provisioning_service._translate_exception(exc, "grant_subscription_sync")
                await self.provisioning_service._maybe_enqueue_retry(account.id, plan.plan_id, new_expiry, translated_exc)

            return account, sync_status, profile.provisioning_state.value

        except Exception as exc:
            await self.account_repo.session.rollback()
            logger.error("Failed to grant subscription for account %s: %s", account_id_str, exc)
            if isinstance(exc, AdminServiceError):
                raise
            raise AdminServiceError("Database error during subscription grant") from exc

        logger.info("Administrative subscription grant completed for %s. Sync status: %s", account_id_str, sync_status)
        return account, sync_status, profile.provisioning_state.value

    # ── Session management ───────────────────────────────────────────────────

    async def logout_all(self, account_id_str: str) -> int:
        """
        Revoke all active refresh tokens for the given account.
        Returns the count of revoked sessions.
        """
        account = await self._get_by_account_id(account_id_str)
        try:
            count = await self.refresh_repo.revoke_all_for_account(account.id)
        except RepositoryError as exc:
            logger.error("Repository error revoking all sessions")
            raise AdminServiceError(
                "Database error revoking sessions for account"
            ) from exc
        logger.info("Administrative logout-all executed.")
        return count
