# ADR-007: Why SELECT FOR UPDATE is Required for Token Rotation

**Status:** Accepted
**Date:** 2026-07-03
**Phase:** 1.3.4 — Refresh Token Rotation Engine

---

## Context

During Refresh Token Rotation (`rotate_refresh_token`), the service looks up the existing refresh token by hash, verifies its expiration and revocation status, marks it as revoked, and generates a new refresh token.

In an asynchronous API server handling concurrent HTTP requests, a client (or an attacker) might send multiple identical refresh requests simultaneously (e.g., due to race conditions, retry loops, or aggressive multi-threading).

Without database-level concurrency control, two concurrent requests could execute as follows:
1. Request A reads `token_hash` -> sees `is_revoked = False`.
2. Request B reads `token_hash` -> sees `is_revoked = False` (before Request A commits).
3. Request A marks token revoked, generates New Token 1, commits -> Success.
4. Request B marks token revoked, generates New Token 2, commits -> Success.

This race condition allows a single refresh token to spawn multiple valid child tokens, violating the single-use rotation invariant and bypassing replay detection.

---

## Decision

**Always use explicit row-level database locking (`SELECT ... FOR UPDATE`) when querying a refresh token during rotation.**

In SQLAlchemy / Repository layer:
```python
await self.repo.get_by_hash(token_hash, for_update=True)
# Translates to: SELECT ... FROM refresh_tokens WHERE token_hash = $1 FOR UPDATE
```

---

## Consequences

**Positive:**
- Complete race condition immunity: When Request A executes `SELECT ... FOR UPDATE`, PostgreSQL places an exclusive row lock on the refresh token row. If Request B arrives concurrently with the same token hash, PostgreSQL blocks Request B until Request A's transaction finishes (commit or rollback).
- Strict serialization: Once Request A commits, Request B unblocks, re-reads the row, and immediately sees `is_revoked = True`. This correctly triggers the Replay Attack Detection logic (`RefreshTokenReplayError`) and revokes all sessions instead of spawning a duplicate valid token.
- Guaranteed atomicity and single-use rotation without requiring application-level distributed locks (e.g., Redis mutexes).

**Negative:**
- Concurrent refresh requests for the *same* token will block at the database layer until the lock is released, adding latency to contention scenarios. However, legitimate clients should never send concurrent refresh requests for the exact same token.
- Requires transaction awareness: `SELECT FOR UPDATE` must be executed within an active database transaction (`async with session.begin():` or session commit boundary) to hold the lock until completion.

---

## Alternatives Considered

### Application-Level In-Memory Locking (asyncio.Lock or Mutex)
**Rejected.** In-memory locks only work within a single Python process. In a multi-worker or multi-container production deployment (e.g., Uvicorn with 4 workers, or horizontally scaled Docker containers), in-memory locks provide zero protection against race conditions across processes.

### Optimistic Concurrency Control (Version Columns / CAS)
**Rejected.** We could add a `version` column and update `WHERE id = $1 AND version = $2`. If rows affected == 0, raise a concurrent modification error. While valid, pessimistic locking (`FOR UPDATE`) is simpler to reason about in our linear rotation transaction and directly integrates with PostgreSQL's ACID guarantees without requiring application retry loops.

### Distributed Locking (Redis Redlock)
**Rejected.** Introducing Redis solely for mutex locking adds unnecessary operational overhead and infrastructure dependency to a project of this size. PostgreSQL row locking handles this workload natively and reliably.
