# ADR-004: Repository Pattern Instead of Direct SQL

**Status:** Accepted
**Date:** 2026-07-03
**Phase:** 1.3.1 — Foundation

---

## Context

The billing server needs to persist and retrieve accounts, devices, and refresh tokens. The question is how database access should be structured:

1. **Direct SQL in services** — service methods call `session.execute(select(...))` inline.
2. **ORM methods in services** — service methods call `session.get()`, `session.add()` inline.
3. **Repository pattern** — a dedicated `*Repository` class encapsulates all database queries for a model. Services receive repository instances via dependency injection.

---

## Decision

**Implement a repository pattern (`BaseRepository` + model-specific subclasses).**

```
Services → Repositories → SQLAlchemy AsyncSession → PostgreSQL
```

Services depend on repository interfaces, not on sessions or SQL directly.

---

## Consequences

**Positive:**
- Services are completely isolated from SQLAlchemy internals, SQL dialects, session lifecycle, and ORM-specific exceptions. `AuthenticationService` never imports `AsyncSession`, `select`, or `SQLAlchemyError`.
- All SQLAlchemy exceptions (`IntegrityError`, `SQLAlchemyError`) are caught in the repository layer and translated into domain exceptions (`DuplicateEntityError`, `DatabaseOperationError`). Services only ever handle domain exceptions.
- Repository methods can be mocked in unit tests with `unittest.mock.patch.object()`, allowing service logic to be tested independently of a database.
- Changing the ORM version, switching from PostgreSQL to another database, or changing query strategies only requires changes in the repository layer — service logic is unaffected.
- `BaseRepository` provides reusable `create()`, `update()`, `delete()`, `get_by_id()`, `exists()` methods, reducing per-model boilerplate.

**Negative:**
- Additional abstraction layer adds files and classes (3 repository files vs. inline SQL).
- Developers must maintain the layer discipline: services must not receive `AsyncSession` directly or call SQLAlchemy methods themselves.
- For complex analytical queries (aggregations, joins across many tables), the repository pattern can become awkward. At our scale this is not currently a concern.

---

## Alternatives Considered

### Direct SQLAlchemy in Services
**Rejected.** Services become coupled to ORM internals. `SQLAlchemyError` propagation through service layers creates HTTP-layer knowledge requirements in domain logic (what HTTP status does an `IntegrityError` map to?). Testing requires a real database session for every service test.

### Raw SQL (psycopg3 without ORM)
**Not selected.** Raw SQL provides maximum query control but eliminates automatic schema management via Alembic migrations. The ORM model-first approach is more maintainable at our current scale and team size.

### Active Record Pattern (models with built-in persistence methods)
**Not selected.** Active Record tightly couples model classes to database access, making unit testing difficult and violating the domain model / persistence separation principle.
