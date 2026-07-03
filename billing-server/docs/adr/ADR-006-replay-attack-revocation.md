# ADR-006: Why Replay Attacks Revoke All Sessions

**Status:** Accepted
**Date:** 2026-07-03
**Phase:** 1.3.4 — Refresh Token Rotation Engine

---

## Context

In our Refresh Token Rotation (RTR) scheme, every time a client refreshes their access token, the current refresh token is marked as revoked (`is_revoked = True`) and a new refresh token is issued.

If a client presents a refresh token that is already marked `is_revoked = True`, a **replay attack** or token reuse event has occurred. The system must decide how to respond:
1. Deny the request silently or with a simple error (only affect the attempted token).
2. Revoke only the new token chain that originated from the reused token.
3. Revoke **all** active sessions (all refresh tokens) across the entire account.

---

## Decision

**When token reuse (`is_revoked == True`) is detected, the system revokes ALL active sessions (`is_revoked = True` for all tokens belonging to `account_id`) and raises `RefreshTokenReplayError`.**

---

## Consequences

**Positive:**
- Maximum security containment: When an already-revoked refresh token is presented, it is mathematically impossible for the server to determine whether the attacker or the legitimate client presented the old token vs. the new token. By revoking all sessions across the account, any attacker who stole a refresh token is immediately locked out, regardless of who rotated the token first.
- Forces the legitimate user to re-authenticate with their Master Token, alerting them (by UX friction or explicit notification) that their session state was disrupted.
- Adheres to RFC 6749 and modern OAuth 2.0 / BCP (Best Current Practice) recommendations for refresh token rotation.

**Negative:**
- Aggressive revocation can cause false positives under unstable network conditions (e.g., mobile network handoffs or VPN disconnects where a client successfully sent a refresh request, the server rotated the token, but the client dropped offline before receiving the response). When the client retries with the old token, all devices on the account are logged out.
- Future mitigation: We may introduce a short time-window grace period (e.g., 30–60 seconds) for network retry idempotency if real-world telemetry shows excessive false-positive disconnects. Currently, strict zero-tolerance security is prioritized.

---

## Alternatives Considered

### Ignore and Reject Simply (No Mass Revocation)
**Rejected.** If an attacker steals a refresh token and uses it after the legitimate client has rotated it, simply rejecting the old token does nothing to stop the attacker, who already possesses the active rotated token (or vice-versa). The compromised session would remain active for up to 30 days.

### Revoke Only the Specific Device/Session Chain
**Rejected.** Tracking token lineage/family chains across multiple rotations adds complex recursive database queries or self-referential foreign keys (`parent_token_hash`). Furthermore, if an attacker stole a token on Laptop A, revoking only Laptop A's session chain is fine, but account-wide revocation provides a cleaner security guarantee without schema complexity.
