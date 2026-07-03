"""
authentication.py — Core Authentication Service

Provides a pure domain service responsible for answering:
"Can this Account ID + Master Token authenticate?"

ARCHITECTURE & DESIGN DECISIONS:
1. Why authentication returns a typed result instead of bool:
   Returning a simple boolean (`True`/`False`) cannot differentiate between failure modes (e.g., non-existent account
   vs. invalid token vs. expired subscription vs. suspended subscription). A typed result (`AuthenticationResult`
   containing an `AuthenticationReason` enum) provides clear, structured reasons that allow upper layers (like API endpoints
   or audit loggers) to handle each case appropriately (e.g., returning specific error messages or status codes) while
   keeping the core authentication service strictly decoupled from HTTP protocol details and status codes.

2. Why account enumeration resistance matters (Timing Attack Defense):
   If checking a non-existent account returned immediately without hashing the provided Master Token, an attacker could send
   thousands of authentication requests with random Account IDs and measure response execution times. Requests taking ~1ms
   would indicate non-existent accounts, whereas requests taking ~3ms (due to SHA-256 hashing) would reveal valid Account IDs.
   By performing `verify_master_token` against a dummy hash when `account is None`, we ensure the execution time is
   approximately identical to a valid account lookup, completely preventing account enumeration via network timing side channels.

3. Why repositories are used instead of direct SQL:
   Repositories (`AccountRepository`) encapsulate database access, queries, and SQLAlchemy session management. By depending only
   on the repository layer, the authentication service remains isolated from schema internals, SQL dialects, and session
   lifecycle management, while ensuring all database errors are cleanly translated into domain service exceptions without
   leaking ORM internals.

4. Why we avoid premature optimization:
   This service is expected to handle tens or hundreds of authentications per minute, not millions. Favoring clear, auditable,
   and linear code over clever performance hacks ensures maintainability and directly contributes to thorough security reviews.
"""
from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.exceptions import RepositoryError
from app.models.account import Account
from app.models.base import SubscriptionStatus
from app.repositories.account_repository import AccountRepository
from app.security import verify_master_token, SHA256_HEX_LENGTH
from app.services.exceptions import AuthenticationServiceError

logger = logging.getLogger(__name__)

# Dummy SHA-256 hash used for constant-time timing attack defense when an account does not exist.
# 64 hexadecimal zero characters matching the format of a valid Master Token hash.
DUMMY_MASTER_TOKEN_HASH: str = "0" * SHA256_HEX_LENGTH


class AuthenticationReason(str, enum.Enum):
    """
    Structured reasons for authentication outcomes.
    Avoids returning arbitrary strings or ambiguous booleans.
    """
    SUCCESS = "SUCCESS"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    INVALID_MASTER_TOKEN = "INVALID_MASTER_TOKEN"
    SUBSCRIPTION_EXPIRED = "SUBSCRIPTION_EXPIRED"
    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"
    ACCOUNT_PENDING = "ACCOUNT_PENDING"


@dataclass(frozen=True)
class AuthenticationResult:
    """
    Typed result returned by AuthenticationService.authenticate().
    Encapsulates success status, structured reason enum, and the authenticated Account model (if applicable).
    """
    success: bool
    reason: AuthenticationReason
    account: Account | None = None


class AuthenticationService:
    """
    Core authentication service class.
    Strictly independent of FastAPI routes, Request/Response objects, JWTs, refresh tokens, and middleware.
    """

    def __init__(self, account_repository: AccountRepository) -> None:
        self.account_repo = account_repository

    async def authenticate(self, account_id: str, master_token: str) -> AuthenticationResult:
        """
        Authenticate an Account ID and Master Token credential pair against repository state.

        Performs the following sequence:
        1. Lookup account by Account ID (using repository).
        2. If account not found -> execute timing attack defense -> return ACCOUNT_NOT_FOUND.
        3. Verify Master Token against stored SHA-256 hash -> if invalid -> return INVALID_MASTER_TOKEN.
        4. Check subscription status -> if SUSPENDED or PENDING -> return respective failure reason.
        5. Check subscription expiry timestamp -> if expired -> return SUBSCRIPTION_EXPIRED.
        6. Return SUCCESS with authenticated account.

        LOGGING INVARIANT:
        Never logs Account IDs, Master Tokens, or token hashes. Logs only generic outcome descriptions.
        """
        # Step 1: Find Account via repository
        try:
            account = await self.account_repo.get_by_account_id(account_id)
        except RepositoryError as e:
            logger.error("Authentication failed due to repository error")
            raise AuthenticationServiceError("Database error during authentication lookup", detail=str(e)) from e
        except Exception as e:
            logger.error("Authentication failed due to unexpected database error")
            raise AuthenticationServiceError("Unexpected database error during authentication lookup", detail=str(e)) from e

        # Step 2: Not Found check with Timing Attack Defense
        if account is None:
            # TIMING ATTACK DEFENSE:
            # Always execute verify_master_token against a dummy hash so that hashing and constant-time
            # comparison execute even when the account does not exist. This prevents account enumeration
            # based on response timing differences.
            verify_master_token(master_token, DUMMY_MASTER_TOKEN_HASH)
            logger.info("Authentication failed: invalid credentials")
            return AuthenticationResult(
                success=False,
                reason=AuthenticationReason.ACCOUNT_NOT_FOUND,
                account=None,
            )

        # Step 3: Verify Master Token
        if not verify_master_token(master_token, account.master_token_hash):
            logger.info("Authentication failed: invalid credentials")
            return AuthenticationResult(
                success=False,
                reason=AuthenticationReason.INVALID_MASTER_TOKEN,
                account=None,
            )

        # Step 4: Subscription Status check
        if account.status == SubscriptionStatus.SUSPENDED:
            logger.info("Authentication failed: suspended account")
            return AuthenticationResult(
                success=False,
                reason=AuthenticationReason.ACCOUNT_SUSPENDED,
                account=account,
            )

        if account.status == SubscriptionStatus.PENDING:
            logger.info("Authentication failed: pending subscription")
            return AuthenticationResult(
                success=False,
                reason=AuthenticationReason.ACCOUNT_PENDING,
                account=account,
            )

        if account.status == SubscriptionStatus.EXPIRED:
            logger.info("Authentication failed: expired subscription")
            return AuthenticationResult(
                success=False,
                reason=AuthenticationReason.SUBSCRIPTION_EXPIRED,
                account=account,
            )

        if account.status != SubscriptionStatus.ACTIVE:
            logger.info("Authentication failed: expired subscription")
            return AuthenticationResult(
                success=False,
                reason=AuthenticationReason.SUBSCRIPTION_EXPIRED,
                account=account,
            )

        # Step 5: Subscription Expiry timestamp check
        if account.subscription_expires_at is not None:
            now = datetime.now(timezone.utc)
            expires_at = account.subscription_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now >= expires_at:
                logger.info("Authentication failed: expired subscription")
                return AuthenticationResult(
                    success=False,
                    reason=AuthenticationReason.SUBSCRIPTION_EXPIRED,
                    account=account,
                )

        # Step 6: Authentication Success
        logger.info("Authentication succeeded")
        return AuthenticationResult(
            success=True,
            reason=AuthenticationReason.SUCCESS,
            account=account,
        )
