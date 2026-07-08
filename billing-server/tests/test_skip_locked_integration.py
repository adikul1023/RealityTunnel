"""
test_skip_locked_integration.py — PostgreSQL integration tests for SKIP LOCKED behavior
and get_stale_profiles cutoff window logic.

These tests run directly against a live PostgreSQL instance (same as all other DB tests).
They prove database-level locking semantics, not just argument passing.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Account, ProvisioningProfile, ProvisioningState
from app.repositories import AccountRepository, ProvisioningRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_account_and_profile(
    session: AsyncSession,
    *,
    account_suffix: str,
    last_sync_at: datetime,
    state: ProvisioningState = ProvisioningState.ACTIVE,
) -> ProvisioningProfile:
    """Insert an Account + ProvisioningProfile row and commit inside the given session."""
    acc_repo = AccountRepository(session)
    account = await acc_repo.create(
        account_id=f"SKIP-{account_suffix}",
        master_token_hash=f"hash_skip_{account_suffix}_{uuid.uuid4().hex}",
        plan_id="basic",
        commit=True,
    )
    prov_repo = ProvisioningRepository(session)
    profile = await prov_repo.create(
        account_id=account.id,
        remote_user_id=f"remote_skip_{account_suffix}",
        provisioning_state=state,
        last_sync_at=last_sync_at,
        commit=True,
    )
    return profile


async def _cleanup_test_accounts(session: AsyncSession, account_id_prefixes: list[str]) -> None:
    """Delete test accounts by account_id prefix (cascades to profiles)."""
    for prefix in account_id_prefixes:
        await session.execute(
            text("DELETE FROM accounts WHERE account_id LIKE :prefix"),
            {"prefix": f"{prefix}%"},
        )
    await session.commit()


# ---------------------------------------------------------------------------
# Test 1: SKIP LOCKED — two concurrent workers get non-overlapping rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skip_locked_prevents_overlap_between_concurrent_workers():
    """
    Integration test: prove PostgreSQL SKIP LOCKED prevents two concurrent
    scheduler workers from acquiring the same rows.

    Setup:    10 ACTIVE provisioning profiles, all stale.

    Sequencing (strict):
      1. Worker A begins a transaction and issues SELECT ... FOR UPDATE SKIP LOCKED.
         It signals Worker B that locks are held, then WAITS.
      2. Worker B receives the signal, issues SELECT ... FOR UPDATE SKIP LOCKED
         on the same table while A still holds its locks. B records what it gets,
         then signals A that it is done.
      3. Worker A receives B's done signal and rolls back (releasing all locks).

    Assert: zero overlap between A's locked set and B's visible set.
    """
    now = datetime.now(timezone.utc)
    stale = now - timedelta(hours=2)
    suffixes = [f"SL{i:02d}" for i in range(10)]
    account_id_prefixes = ["SKIP-SL"]
    profile_ids: list[uuid.UUID] = []

    # --- pre-test cleanup: remove any leftover rows from prior runs ---
    async with AsyncSessionLocal() as pre_session:
        await _cleanup_test_accounts(pre_session, account_id_prefixes)

    # --- seed: insert 10 profiles in one session, committed ---
    async with AsyncSessionLocal() as seed_session:
        for suffix in suffixes:
            p = await _create_account_and_profile(
                seed_session,
                account_suffix=suffix,
                last_sync_at=stale,
                state=ProvisioningState.ACTIVE,
            )
            profile_ids.append(p.id)

    worker_a_ids: set[uuid.UUID] = set()
    worker_b_ids: set[uuid.UUID] = set()

    # Two events for strict handshake:
    #   a_locked  — set by A after it has acquired FOR UPDATE locks
    #   b_done    — set by B after it has finished its query
    a_locked = asyncio.Event()
    b_done = asyncio.Event()

    async def worker_a() -> None:
        async with AsyncSessionLocal() as session_a:
            repo_a = ProvisioningRepository(session_a)
            # Step 1: acquire row-level locks with SKIP LOCKED.
            rows = await repo_a.get_stale_profiles(now, for_update=True, skip_locked=True)
            for r in rows:
                worker_a_ids.add(r.id)
            # Step 2: tell B that locks are held.
            a_locked.set()
            # Step 3: wait until B has finished querying.
            await b_done.wait()
            # Step 4: rollback releases all FOR UPDATE locks.
            await session_a.rollback()

    async def worker_b() -> None:
        # Step 1: wait until A holds its locks.
        await a_locked.wait()
        async with AsyncSessionLocal() as session_b:
            repo_b = ProvisioningRepository(session_b)
            # Step 2: query with SKIP LOCKED — A's rows must be invisible.
            rows = await repo_b.get_stale_profiles(now, for_update=True, skip_locked=True)
            for r in rows:
                worker_b_ids.add(r.id)
            await session_b.rollback()
        # Step 3: signal A that B is done.
        b_done.set()

    await asyncio.gather(worker_a(), worker_b())

    # --- assert: all 10 rows visible across A+B, with zero overlap ---
    all_seen = worker_a_ids | worker_b_ids
    overlap = worker_a_ids & worker_b_ids

    # Each of the 10 seeded profiles must appear in exactly one worker's set.
    for pid in profile_ids:
        assert pid in all_seen, f"Profile {pid} was seen by neither worker"

    assert len(overlap) == 0, (
        f"SKIP LOCKED failure: {len(overlap)} row(s) acquired by BOTH workers. "
        f"Overlapping IDs: {overlap}"
    )

    # --- cleanup ---
    async with AsyncSessionLocal() as cleanup_session:
        await _cleanup_test_accounts(cleanup_session, account_id_prefixes)


# ---------------------------------------------------------------------------
# Test 2: get_stale_profiles cutoff boundary — 61 min included, 59 min excluded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_stale_profiles_cutoff_boundary():
    """
    Integration test: prove that get_stale_profiles uses last_sync_at <= cutoff,
    meaning exactly:
      - last_sync_at = now - 61 min  → included  (stale, must be returned)
      - last_sync_at = now - 59 min  → excluded  (fresh, must NOT be returned)
      - last_sync_at = exactly cutoff → included  (boundary, must be returned)

    This directly validates the 60-minute window used by run_provisioning_reconciliation_job.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=60)

    stale_61 = now - timedelta(minutes=61)    # must appear
    fresh_59 = now - timedelta(minutes=59)    # must NOT appear
    boundary = cutoff                          # must appear (inclusive boundary)

    account_id_prefixes = ["SKIP-CB"]

    async with AsyncSessionLocal() as session:
        p_stale = await _create_account_and_profile(
            session,
            account_suffix="CB01",
            last_sync_at=stale_61,
        )
        p_fresh = await _create_account_and_profile(
            session,
            account_suffix="CB02",
            last_sync_at=fresh_59,
        )
        p_boundary = await _create_account_and_profile(
            session,
            account_suffix="CB03",
            last_sync_at=boundary,
        )

    async with AsyncSessionLocal() as query_session:
        repo = ProvisioningRepository(query_session)
        results = await repo.get_stale_profiles(cutoff)
        result_ids = {r.id for r in results}

    assert p_stale.id in result_ids, (
        "Profile synced 61 minutes ago should be returned by get_stale_profiles "
        f"(cutoff={cutoff}, last_sync_at={stale_61})"
    )
    assert p_boundary.id in result_ids, (
        "Profile synced exactly at cutoff should be returned (inclusive boundary). "
        f"(cutoff={cutoff}, last_sync_at={boundary})"
    )
    assert p_fresh.id not in result_ids, (
        "Profile synced 59 minutes ago must NOT be returned by get_stale_profiles "
        f"(cutoff={cutoff}, last_sync_at={fresh_59})"
    )

    # --- cleanup ---
    async with AsyncSessionLocal() as cleanup_session:
        await _cleanup_test_accounts(cleanup_session, account_id_prefixes)
