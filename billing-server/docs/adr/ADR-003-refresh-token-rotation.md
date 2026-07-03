# ADR-003: Refresh Token Rotation Instead of Long-Lived JWTs

**Status:** Accepted
**Date:** 2026-07-03
**Phase:** 1.3.4 — Refresh Token Rotation Engine

---

## Context

The system needs persistent login sessions — users should not need to re-enter their Account ID and Master Token every 15 minutes. Two broad strategies exist:

1. **Long-lived JWTs** — issue a single JWT with a 30-day or permanent lifetime.
2. **Refresh Token Rotation (RTR)** — issue a short-lived Access JWT (15 min) + a long-lived, database-backed Refresh Token (30 days). The refresh token is exchanged for a new access token + new refresh token on expiry.

---

## Decision

**Implement Refresh Token Rotation (RTR).**

- Access tokens: Ed25519-signed JWTs, 15-minute lifetime, stateless
- Refresh tokens: 256-bit CSPRNG, 30-day lifetime, stored as SHA-256 hashes in PostgreSQL
- Every refresh call rotates the refresh token (old invalidated, new issued)
- Reuse of a revoked refresh token triggers account-wide session revocation

---

## Consequences

**Positive:**
- Access tokens expire in 15 minutes. If an access token is intercepted (e.g., via a logging system, proxied request, client-side vulnerability), the attacker's window is bounded at 15 minutes with no database interaction required by the victim.
- Refresh tokens can be individually revoked by marking them `is_revoked=True` in the database. Individual session revocation (logout from one device) is possible. Account-wide revocation (logout-all) is a single bulk update.
- If a refresh token is stolen and used by an attacker, the legitimate client will detect the replay (their token is now `is_revoked`) and the system responds with account-wide revocation.
- Token rotation limits the exposure window for stolen tokens to the period between legitimate refresh calls — typically 15 minutes or less.
- Database-backed refresh tokens allow server-side session management: operators can revoke sessions, inspect active sessions, and enforce device limits.

**Negative:**
- Increased database writes (one INSERT + one UPDATE per refresh cycle, plus the SELECT FOR UPDATE).
- Increased code complexity compared to long-lived JWTs — the rotation service, replay detection, and atomic transaction logic are non-trivial.
- Refresh token rotation can fail under poor network conditions: if the client receives the rotated token but fails to persist it before crash, the next rotation will trigger a replay detection false positive and log the user out. This is a known edge case; the mitigation is a short grace period or idempotent rotation key (not yet implemented).

---

## Alternatives Considered

### Long-Lived JWTs (30-day lifetime)
**Rejected.** A stolen 30-day JWT cannot be revoked — it remains valid until expiry. Since JWTs are stateless, there is no database record to mark invalid. The only remediation for a stolen long-lived JWT is key rotation (which invalidates ALL tokens system-wide). Long-lived JWTs also cannot support per-device logout.

### Short-Lived JWTs + Re-Authentication
**Rejected.** Requiring users to re-enter credentials every 15 minutes is not acceptable UX for a VPN client that runs continuously in the background.

### Opaque Session Tokens (traditional server-side sessions)
**Not selected.** Pure server-side sessions require a database lookup on every API request to validate the session, which adds latency and database load. The hybrid approach (stateless access JWT for frequent endpoint calls, database-backed refresh token for session persistence) provides the best tradeoff.
