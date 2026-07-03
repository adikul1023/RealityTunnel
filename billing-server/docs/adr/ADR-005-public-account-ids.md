# ADR-005: Why Account IDs are Public Identifiers

**Status:** Accepted
**Date:** 2026-07-03
**Phase:** 1.3.1 / 1.3.2 — Authentication Subsystem

---

## Context

In RealityTunnel, users identify themselves during login with an **Account ID** (formatted as `RT-XXXX-XXXX-XXXX`) and a **Master Token** (256-bit hexadecimal string). 

The system must decide how to treat the Account ID: is it a secret credential (like a password or token) that must be hidden and protected, or is it a public identifier (like a username or email address)?

---

## Decision

**Account IDs are treated as public identifiers.**

- Account IDs can be safely displayed in user interfaces, invoices, support tickets, and QR codes.
- Security relies entirely on the 256-bit Master Token (and derived tokens like JWTs and Refresh Tokens), not on the secrecy of the Account ID.
- Account ID generation uses an unambiguous 31-character alphabet (`ABCDEFGHJKMNPQRSTUVWXYZ23456789`) excluding visually similar characters (`0`, `O`, `1`, `I`, `L`) to facilitate manual reading and customer support communication.

---

## Consequences

**Positive:**
- Users can easily copy, share, and communicate their Account ID to customer support without compromising their account security.
- Account IDs can be safely embedded in non-sensitive logs, QR codes for quick VPN setup, and client billing portals.
- Formatting as 3 groups of 4 characters (`RT-XXXX-XXXX-XXXX`) makes visual verification and manual entry error-resistant.

**Negative:**
- Because Account IDs are public, an attacker can attempt to enumerate or target specific Account IDs. This necessitates timing attack defenses (see `ADR-001` and `authentication.py` DUMMY_MASTER_TOKEN_HASH defense) to ensure attackers cannot even verify whether a specific Account ID exists in the system via timing side channels.

---

## Alternatives Considered

### Secret Account IDs (No Master Token)
**Rejected.** If the Account ID itself were the sole secret (e.g., a single long token), sharing it with customer support or printing it on an invoice would result in total account compromise. Separating the public identity (Account ID) from the secret credential (Master Token) is standard security practice.

### Email Address as Identifier
**Rejected.** Privacy-focused VPN users often do not wish to provide an email address. Generating a random Account ID allows anonymous account creation via cryptocurrency or privacy-preserving payment methods while maintaining unique user identification.
