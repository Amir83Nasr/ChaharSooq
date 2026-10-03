# ADR 003 — PostgreSQL + SQLAlchemy 2.x + Alembic

Date: 2026-10-04 · Status: accepted

## Context

Product needs relational integrity for catalog/orders with machine-readable numerics and datetimes.

## Decision

- PostgreSQL 17, SQLAlchemy 2.x typed mappings, Alembic migrations, layered flow Routes→Services→Repositories→DB.
- Prices integer toman, datetimes tz-aware UTC; Persian formatting UI-only.

## Alternatives

- SQLite-only / JSON columns: rejected — weak integrity, spec requires Postgres + migrations.
- ORM-less raw SQL: rejected — higher injection/maintenance cost without proven need.

## Consequences

- Every schema change ships a migration; indexes follow query patterns; tests default SQLite with Postgres parity in CI.
