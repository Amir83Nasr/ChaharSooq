# Database — چهارسوق

PostgreSQL 17 + SQLAlchemy 2.x (`Mapped`/`mapped_column`) + Alembic (`backend/api/alembic.ini`, `backend/api/migrations/env.py`).

Tables: `admins`, `admin_sessions` (indexed `expires_at`, token SHA-256 unique), `products` (indexed `created_at`, unique `sku`).

Rules:

- Prices are integer toman; datetimes tz-aware UTC. Never store Persian digits or Jalali strings.
- Schema changes via Alembic migrations only.
- Indexes follow query patterns (`expires_at`, `created_at`); FKs/constraints added as the domain grows.
- Transactions: one commit per request in `get_session()` (commit on success, rollback on error).
- Tests use in-memory SQLite via `DATABASE_URL` override; CI runs Postgres service for integration parity.
