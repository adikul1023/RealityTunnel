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
from app.models.base import SubscriptionStatus
from app.repositories.account_repository import AccountRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
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
    ) -> None:
        self.account_repo = account_repo
        self.refresh_repo = refresh_repo

    # ── Private helpers ─────────────────────────────────────────────────────

    async def _get_by_account_id(self, account_id_str: str) -> Account:
        """
        Internal lookup by human-readable account_id string.
        Raises AdminAccountNotFoundError if not found, AdminServiceError on DB failure.
        """
        try:
            account = await self.account_repo.get_by_account_id(account_id_str)
        except RepositoryError as exc:
            logger.error("Repository error during admin account lookup")
            raise AdminServiceError("Database error during administrative account lookup") from exc

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
        account = await self._get_by_account_id(account_id_str)
        try:
            account = await self.account_repo.update(account, status=SubscriptionStatus.SUSPENDED)
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
        account = await self._get_by_account_id(account_id_str)
        try:
            account = await self.account_repo.update(account, status=SubscriptionStatus.ACTIVE)
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

        account = await self._get_by_account_id(account_id_str)

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
            raise AdminServiceError("Database error revoking sessions for account") from exc
        logger.info("Administrative logout-all executed.")
        return count
