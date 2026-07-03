# Authentication Freeze Document
**RealityTunnel Billing/Auth Server — Phase 1.3 Complete**
**Status: FROZEN** — Do not modify without an architecture review.
**Date frozen: 2026-07-03** | **Git tag: phase-1.3-authentication-complete**

---

## Purpose

This document describes the final, audited architecture of the Authentication subsystem (phases 1.3.1–1.3.8). It is the reference for all future work that depends on authentication. A developer reading this six months from now should understand the design without reading source code first.

---

## Component Map

```
app/
├── security/
│   ├── constants.py         Token sizes, alphabets, expiry constants
│   ├── tokens.py            CSPRNG generation (master token, refresh token, device GUID, account ID)
│   ├── crypto.py            SHA-256 hashing + hmac.compare_digest constant-time comparison
│   ├── jwt_models.py        AccessTokenClaims + JWT algorithm/issuer/audience constants
│   └── jwt_service.py       JWTService — Ed25519 key management, issuance, verification
│
├── services/
│   ├── exceptions.py        Domain exception hierarchy (no HTTP coupling)
│   ├── authentication.py    AuthenticationService — lookup, timing defense, status validation
│   └── refresh_tokens.py    RefreshTokenService — RTR, replay detection, atomic rotation
│
├── repositories/
│   ├── base.py              Generic async CRUD with domain exception translation
│   ├── account_repository.py
│   └── refresh_token_repository.py   hash lookup, revoke, bulk revoke
│
├── models/
│   ├── base.py              SubscriptionStatus enum, TimestampMixin
│   ├── account.py           accounts table
│   ├── device.py            devices table
│   └── refresh_token.py     refresh_tokens table
│
├── routers/
│   ├── auth_models.py       HTTP DTOs (LoginRequest, LoginResponse, RefreshRequest, …)
│   └── auth.py              POST /login  /refresh  /logout  /logout-all   GET /me
│
├── dependencies.py          DI providers — JWTService singleton, session-scoped repos/services
├── main.py                  FastAPI app — exception handlers, router mounting
└── config.py                pydantic-settings — environment, secrets, database URL
```

---

## Flow 1 — Login

**Endpoint:** `POST /api/auth/login`

```
Client
  │  LoginRequest { account_id, master_token, device_guid }
  ▼
auth.py::login()
  ├─► AuthenticationService.authenticate(account_id, master_token)
  │     ├─► AccountRepository.get_by_account_id(account_id)
  │     │     SELECT * FROM accounts WHERE account_id = $1
  │     │
  │     ├─► [account is None]
  │     │     verify_master_token(token, DUMMY_MASTER_TOKEN_HASH="0"*64)
  │     │     ← constant-time SHA-256 + hmac.compare_digest — always fails
  │     │     ← timing indistinguishable from valid-account path
  │     │     return AuthenticationResult(success=False, ACCOUNT_NOT_FOUND)
  │     │
  │     ├─► verify_master_token(token, account.master_token_hash)
  │     │     SHA-256(token) → hmac.compare_digest(hash, stored_hash)
  │     │
  │     ├─► Status checks: SUSPENDED → fail | PENDING → fail | EXPIRED → fail
  │     │                  subscription_expires_at < now() → fail
  │     │
  │     └─► return AuthenticationResult(success=True, account=account)
  │
  ├─► JWTService.issue_access_token(uuid, account_id, device_guid)
  │     see Flow 3
  │
  ├─► RefreshTokenService.issue_refresh_token(account_id, device_guid)
  │     secrets.token_hex(32) → SHA-256 → INSERT refresh_tokens
  │
  └─► LoginResponse { access_token, refresh_token, token_type="Bearer", expires_in=900 }
```

Never returned to client: raw hashes, account UUID, internal DB IDs.

---

## Flow 2 — Refresh Token Rotation (RTR)

**Endpoint:** `POST /api/auth/refresh`

```
Client
  │  RefreshRequest { refresh_token }
  ▼
auth.py::refresh()
  ├─► RefreshTokenService.rotate_refresh_token(refresh_token)
  │     ├─► SHA-256(refresh_token) = token_hash
  │     │
  │     ├─► SELECT * FROM refresh_tokens WHERE token_hash=$1 FOR UPDATE
  │     │   ← exclusive row lock — prevents concurrent rotation race
  │     │
  │     ├─► entity is None → RefreshTokenNotFoundError
  │     │   ← does NOT revoke sessions (prevents DoS via random tokens)
  │     │
  │     ├─► entity.is_revoked == True → REPLAY DETECTED
  │     │   UPDATE all active tokens for account: is_revoked=True
  │     │   → RefreshTokenReplayError
  │     │
  │     ├─► entity.expires_at < now() → RefreshTokenExpiredError
  │     │   ← expired tokens are NOT rotated
  │     │
  │     ├─► ── ATOMIC TRANSACTION ──────────────────────────────────
  │     │     new_token = secrets.token_hex(32)
  │     │     INSERT new token row       (flush — no commit)
  │     │     UPDATE old token is_revoked=True (flush — no commit)
  │     │     session.commit()  ← single atomic commit
  │     │   ── ON EXCEPTION: session.rollback() ─────────────────────
  │     │
  │     └─► return RefreshRotationResult { new_token, expires_at, device_guid, account_id }
  │
  ├─► AuthenticationService.get_active_account_by_uuid(account_id)
  │   ← IMPORTANT: validates account still ACTIVE post-rotation
  │   ← suspended/expired accounts cannot get new access tokens via RTR
  │
  ├─► JWTService.issue_access_token(uuid, account_id, device_guid)
  │
  └─► RefreshResponse { access_token, refresh_token, token_type="Bearer", expires_in=900 }
```

Invariants: old revoked and new inserted in single commit; device_guid preserved unchanged.

---

## Flow 3 — JWT Issuance

```
JWTService.issue_access_token(uuid, account_id, device_guid)
  │
  ├─► Claims:
  │     sub     = str(account_uuid)        ← DB UUID for lookups
  │     account = account_id               ← human-readable RT-XXXX-XXXX
  │     device  = device_guid
  │     iss     = "RealityTunnel Billing/Auth"
  │     aud     = "RealityTunnel Client"
  │     iat, nbf = now (Unix timestamp)
  │     exp     = now + 15 minutes
  │     jti     = secrets.token_hex(16)   ← 128-bit unique token ID
  │
  └─► jwt.encode(payload, ed25519_private_key, algorithm="EdDSA")
```

Algorithm: EdDSA (Ed25519) only. Signing key never leaves the server process.

---

## Flow 4 — JWT Verification (Protected Endpoints)

**Dependency:** `get_current_account()` in `dependencies.py`

```
Authorization: Bearer <token>
  ├─► Missing or malformed header → 401
  │
  ├─► jwt.decode(token, ed25519_public_key,
  │       algorithms=["EdDSA"],             ← whitelist, no algorithm confusion
  │       audience="RealityTunnel Client",
  │       issuer="RealityTunnel Billing/Auth",
  │       leeway=0,                         ← zero clock skew tolerance
  │       options={"require": ["sub","account","device","iss","aud","iat","nbf","exp","jti"]}
  │   )
  │
  ├─► Any JWT error (expired, tampered, wrong issuer, missing claim) → 401
  │
  ├─► AccessTokenClaims.from_dict(payload)  ← validate all 9 claims typed
  │
  ├─► AuthenticationService.get_active_account_by_uuid(UUID(claims.sub))
  │   ← account must still be active in DB (suspension takes effect here)
  │
  └─► return Account model to protected endpoint handler
```

All 401 paths return identical body: `{"detail": "Authentication failed or token invalid"}`.

---

## Timing Attack Defense

DUMMY_MASTER_TOKEN_HASH = "0" * 64   (compile-time constant, never regenerated)

When account not found: verify_master_token(token, DUMMY_MASTER_TOKEN_HASH)
→ forces SHA-256 + hmac.compare_digest — execution time identical to valid path.
→ comparison always fails — but timing is constant regardless of account existence.

MUST remain a compile-time constant. Per-request generation would be fragile.

---

## Replay Attack Handling

Detection: token found in DB AND is_revoked == True.

Response:
  1. Revoke ALL active refresh tokens for the account (account-wide logout)
  2. HTTP 401 (RefreshTokenReplayError)

Why ALL sessions: when replay is detected, at least two parties hold tokens for the same
session history. Safe assumption: account is compromised. Full revocation is the only safe response.

Why unknown tokens do NOT trigger mass revocation:
  Allowing arbitrary strings to trigger mass revocation = unauthenticated DoS logout.
  Unknown tokens → RefreshTokenNotFoundError → 401, no side effects.

---

## Atomic Transaction Guarantees

rotate_refresh_token() performs exactly two DB writes in one transaction:
  1. INSERT new token row         (flush, no commit)
  2. UPDATE old token is_revoked=True  (flush, no commit)
  3. session.commit()             ← single atomic commit

ON EXCEPTION: session.rollback()

Impossible states after any failure:
  - Old revoked + new missing     (client locked out)
  - New inserted + old active     (both valid simultaneously)

---

## Row Locking (SELECT ... FOR UPDATE)

SELECT * FROM refresh_tokens WHERE token_hash = $1 FOR UPDATE

Without this lock: two concurrent requests using the same token could both read
is_revoked=False, both validate, and both rotate — creating two active sessions from one token.

With this lock: the second concurrent request blocks until the first commits,
then sees is_revoked=True → replay detection triggered.

---

## Security Assumptions

| Assumption | Risk if violated |
|---|---|
| DB not publicly accessible | All hashes exposed; direct lookup possible |
| private_key.pem mode 0600 | Token forgery possible |
| Non-root process (UID 1001) | Key/DB access via privilege escalation |
| secrets.token_hex() = OS CSPRNG | Predictable tokens |
| ENVIRONMENT=production in production | Production guard skipped |
| JWT keys pre-provisioned (no auto-gen) | Key material generated without controls |
| DB timestamps in UTC | Expiry comparisons wrong |
| Only API writes refresh_tokens | Race conditions, state corruption |

---

## Trust Boundaries

```
PUBLIC INTERNET (untrusted)
  │  HTTPS/TLS (Caddy)
  ▼
═══════════════════════════════ BOUNDARY ═══
Billing/Auth API (trusted — Server 1)
  │  PostgreSQL TCP (localhost / Docker network)
  ▼
PostgreSQL (trusted storage — Server 1)
═══════════════════════════════ BOUNDARY ═══
  │  WireGuard tunnel (private, encrypted)
  ▼
Marzban API (semi-trusted — Server 2, VPN enforcement)
```

Client is always untrusted. All security state is authoritative in PostgreSQL.
device_guid is client-provided and NOT authenticated at this phase (Phase 1.4 concern).

---

## Components Locked (Require Architecture Review)

| File | Critical Logic | Risk |
|---|---|---|
| security/crypto.py | SHA-256 + hmac.compare_digest | Algorithm change invalidates all hashes |
| security/jwt_service.py | algorithms=["EdDSA"] whitelist | Any expansion enables algorithm confusion |
| security/jwt_models.py | require claim list, 15-min lifetime | Removing claims weakens verification |
| services/authentication.py | DUMMY_MASTER_TOKEN_HASH timing defense | Removal re-enables account enumeration |
| services/refresh_tokens.py | Atomic rotation + replay detection | Split commit or replay bypass = critical |
| repositories/refresh_token_repository.py | with_for_update() | Removal enables concurrent rotation race |
| main.py | auth_exceptions handler mapping | Adding exc.detail to responses leaks state |
| dependencies.py | Uniform 401 message | Different messages enable error enumeration |

---

## Known Gaps (Explicitly Deferred)

| Gap | Target |
|---|---|
| jti access token blocklist | Phase 2+ |
| Rate limiting on /login and /refresh | Before public exposure |
| Audit event logging | Phase 1.5 |
| Device count limits | Phase 1.4.3 |
| device_guid authentication | Phase 1.4 |
| Admin authentication | Phase 1.4.5 |
| GeoIP, impossible travel | Fraud detection (later) |

---

## Revision History

| Date | Change |
|---|---|
| 2026-07-03 | Initial freeze — phases 1.3.1–1.3.8 complete, 93 tests passing |
