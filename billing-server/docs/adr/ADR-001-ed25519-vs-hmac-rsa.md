# ADR-001: Ed25519 (EdDSA) for JWT Access Token Signing

**Status:** Accepted
**Date:** 2026-07-03
**Phase:** 1.3.3 — JWT Service

---

## Context

The Billing/Auth server must sign short-lived Access JWTs (15-minute lifetime) that clients present to protected API endpoints. The choice of signing algorithm determines the security model for token verification across the system — specifically, whether token verification in future services (VPN middleware, client apps) requires access to any secret material.

Three categories of algorithm were evaluated:
1. **HMAC-based (HS256, HS512)** — symmetric, shared secret
2. **RSA-based (RS256, RS512)** — asymmetric, public/private keypair, large keys
3. **EC-based (ES256) and EdDSA (Ed25519)** — asymmetric, elliptic curve, compact keys

---

## Decision

**Use Ed25519 (EdDSA) as the JWT signing algorithm.**

The JWT header is `{"alg": "EdDSA", "typ": "JWT"}`.
The `algorithms=["EdDSA"]` whitelist is enforced in PyJWT decode calls.

---

## Consequences

**Positive:**
- Clean separation of concerns: only the Billing/Auth server holds the private signing key. Future middleware, VPN servers, or client verification libraries only need the public key to verify tokens — they can never forge tokens.
- Ed25519 signatures are 64 bytes — smaller than RS256 (256 bytes) and comparable to ES256 (64 bytes).
- Ed25519 signing and verification are among the fastest asymmetric operations available in the Python `cryptography` library.
- Ed25519 is immune to RSA padding oracle attacks and key-confusion attacks.
- The algorithm whitelist (`algorithms=["EdDSA"]`) in PyJWT prevents the historical "alg:none" and HS256-with-public-key confusion attacks.
- Keys fit in a PEM file (two files: private_key.pem at 0600, public_key.pem at 0644).

**Negative:**
- Ed25519 is not universally supported in all client environments. However, since our clients are a controlled Windows/Android app and a Python backend, this is not a limitation in our system.
- Unlike HS256, key rotation requires key distribution (the new public key must be provided to all verifiers). This is accepted as a future operational concern and does not block the current architecture.

---

## Alternatives Considered

### HS256 (HMAC-SHA256)
**Rejected.** Symmetric algorithm requires every party that verifies tokens to also possess the signing secret. Sharing the secret with future VPN middleware or client-side code would allow those parties to forge arbitrary tokens. The shared-secret model does not scale to a distributed trust hierarchy.

### RS256 (RSA-SHA256)
**Rejected.** RSA keypairs are large (2048–4096 bits minimum for security), slower to sign than Ed25519, and susceptible to padding oracle attacks if misimplemented. For our scale (tens to hundreds of concurrent authentications), RSA is unnecessarily expensive.

### ES256 (ECDSA-SHA256, P-256)
**Not selected.** ES256 is a reasonable choice. Ed25519 was preferred because: (a) Ed25519 has a deterministic signing algorithm (no per-signature randomness required), which eliminates the Sony PS3-style nonce-reuse attack; (b) Ed25519 is widely regarded as the more conservative modern choice for new systems.
