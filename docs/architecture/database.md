# Database — چهارسوق

PostgreSQL 18 + SQLAlchemy 2.x (`Mapped`/`mapped_column`) + Alembic (`backend/api/alembic.ini`, `backend/api/migrations/env.py`).

Tables: `admins`, `admin_sessions` (indexed `expires_at`, token SHA-256 unique), `products` (indexed `created_at`, `is_active`, `price`, `stock`, `category_id`, unique `sku`), `competitor_listings` (unique `(product_id, store)`, indexed `last_success_at`), `competitor_price_observations` (indexed `(listing_id, observed_at)`).

`competitor_price_observations` keeps one successful fetched price per UTC day per link; the
previous day's row is the baseline for the daily price change used by the furniture/carpet
formula. `products.allowed_decrease_percent` / `allowed_increase_percent` hold the per-product
suggested-price clamp (m and n).

Rules:

- Prices are integer toman; datetimes tz-aware UTC. Never store Persian digits or Jalali strings.
- Catalog sync never hard-deletes products; missing rows are soft-deactivated. `competitor_listings.product_id` is `ON DELETE RESTRICT`, so a stray product delete fails instead of erasing curated links.
- Schema changes via Alembic migrations only.
- Indexes follow query patterns (`expires_at`, `created_at`); FKs/constraints added as the domain grows.
- Transactions: one commit per request in `get_session()` (commit on success, rollback on error).
- Tests use in-memory SQLite via `DATABASE_URL` override; CI runs Postgres service for integration parity.

## Environments

Each environment owns a separate database and a separate `DATABASE_URL`:

| Environment | Database                                               |
| ----------- | ------------------------------------------------------ |
| Development | Local PostgreSQL (compose, host `:5433`)               |
| Staging     | Neon                                                   |
| Production  | PostgreSQL managed on the Ubuntu server `market-linux` |

- Migrations run only against the database of the environment being deployed.
- Production migrations are ordered before the new API version and use a single runner; they must
  not race between workers.
- No automatic Production → Staging/Development data transfer is allowed. Real data used outside
  Production requires a controlled, sanitized process.
- The existing dev-to-staging and dev-to-prod sync scripts are explicit manual helpers. The
  `*-prod` targets still describe the Neon-era production database and are not yet validated for
  `market-linux`. See [deployment.md](deployment.md) and
  [ADR 011](../adr/011-three-environment-architecture.md).
