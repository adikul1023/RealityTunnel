# ADR-001: MFA Guard Fail-Closed Behaviour

**Date:** 2026-07-03  
**Status:** Accepted  
**Phase:** 1.4.5

---

## Context

The `AdminAuthenticationService.authenticate()` method checks whether an administrative
account has MFA enabled before issuing an Admin JWT. The implementation uses:

```python
if getattr(admin, "mfa_enabled", None) is not False:
    raise MFANotImplementedYet("MFA for administrative accounts is not yet implemented.")
```

This was a deliberate change from the initially written:

```python
if admin.mfa_enabled:
    raise MFANotImplementedYet(...)
```

---

## Decision

The guard is **fail-closed**: any value other than the Python literal `False` — including
`None`, `0`, missing attribute, or any truthy value — triggers `MFANotImplementedYet`.

### Why `is not False` instead of the truthiness check `if admin.mfa_enabled`

The truthiness check `if admin.mfa_enabled` evaluates `False` only for the following values:
`False`, `0`, `None`, `""`, `[]`, `{}`. This means:

- A migration that sets `mfa_enabled = None` (e.g., making the column nullable by accident)
  would **silently bypass** the MFA check and allow authentication to proceed.
- An ORM layer misread (e.g., the column type changes from `Boolean` to `Integer` and
  returns `0`) would also silently bypass.

The `is not False` identity check ensures that **only the canonical boolean `False`**
grants authentication. Any ambiguous or malformed database value fails closed.

---

## Trade-offs

| Property | `if admin.mfa_enabled` | `if getattr(...) is not False` |
|----------|------------------------|-------------------------------|
| Bypassed by `NULL` migration | **Yes (silent bypass)** | No |
| Bypassed by type confusion | **Yes (`0` bypasses)** | No |
| Locks out admin on data corruption | No (continues) | **Yes** |
| Locks out admin on missing field | No | **Yes** |

The lockout risk is accepted for this system because:

1. This is an **internal admin system**, not a customer-facing endpoint. A brief operational
   lockout is far preferable to a silent authentication bypass.
2. Admin accounts are managed directly by engineers who have database access and can correct
   data issues immediately.
3. The `admin_users` table has a `NOT NULL DEFAULT false` constraint on `mfa_enabled`,
   so `NULL` values from a correctly applied migration are not possible.

---

## Operational Response

If an admin is locked out due to a data issue:

1. Connect directly to PostgreSQL.
2. Run: `UPDATE admin_users SET mfa_enabled = false WHERE username = '<username>';`
3. Re-attempt authentication.

**Do NOT change the guard to a permissive check.** If you need to bypass the MFA block
legitimately (e.g., for testing), create a new admin user with `mfa_enabled = false`.

---

## Future Work

When MFA is implemented (future phase), the guard should be replaced with:

```python
if getattr(admin, "mfa_enabled", None) is True:
    # Validate TOTP / WebAuthn challenge here
    ...
```

At that point, `None` and missing attribute should still fail closed.
