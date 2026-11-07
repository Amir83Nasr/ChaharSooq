# Database — چهارسوق

PostgreSQL 18 + SQLAlchemy 2.x (`Mapped`/`mapped_column`) + Alembic (`backend/api/alembic.ini`, `backend/api/migrations/env.py`).

Tables: `admins`, `admin_sessions` (indexed `expires_at`, token SHA-256 unique), `products` (indexed `created_at`, `is_active`, `price`, `stock`, `category_id`, unique `sku`), `competitor_listings` (unique `(product_id, store)`, indexed `last_success_at`).

Rules:

- Prices are integer toman; datetimes tz-aware UTC. Never store Persian digits or Jalali strings.
- Catalog sync never hard-deletes products; missing rows are soft-deactivated. `competitor_listings.product_id` is `ON DELETE RESTRICT`, so a stray product delete fails instead of erasing curated links.
- Schema changes via Alembic migrations only.
- Indexes follow query patterns (`expires_at`, `created_at`); FKs/constraints added as the domain grows.
- Transactions: one commit per request in `get_session()` (commit on success, rollback on error).
- Tests use in-memory SQLite via `DATABASE_URL` override; CI runs Postgres service for integration parity.
