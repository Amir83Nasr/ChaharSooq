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
- Alembic resolves its URL only through `DatabaseSettings` (`get_database_settings()`), which reads
  `DATABASE_URL` or a `database_url` file under `SECRETS_DIR`. `alembic.ini` deliberately contains
  no database URL, and the full application `Settings` is not required for migrations.
- `APP_ENV=production` requires an explicit, recognised `DEPLOYMENT_ENV`; a missing or unknown
  identity fails before any connection is opened, including in Alembic and offline SQL generation.
- When `DEPLOYMENT_ENV=production` is explicit, the URL must be PostgreSQL with an explicit,
  non-loopback host. A missing database URL, the committed localhost development default, SQLite,
  `localhost`, `127.0.0.0/8`, `::1`, and IPv4-mapped loopback addresses all fail before any
  connection is opened. Errors never include the URL, host, or credentials. Development and
  Staging keep their previous compatibility.
- `RUN_MIGRATIONS_ON_STARTUP` defaults to `true` in Development/Staging and `false` in Production.
  Staging keeps automatic migrations; Production rejects an explicit `true` and uses the
  standalone runner.
- `RUN_OWNER_BOOTSTRAP_ON_STARTUP` follows the same defaults. Production rejects an explicit
  `true` and runs `scripts/bootstrap_owner.py` explicitly after migrations.
- Production migrations are ordered before the new API version and use a single locked runner;
  they must not race between workers. The runner infrastructure exists in this repository, but the
  Production deployment workflow is still open.
- No automatic Production → Staging/Development data transfer is allowed. Real data used outside
  Production requires a controlled, sanitized process.
- The existing dev-to-staging sync script is an explicit manual helper. The legacy `*-prod` targets
  were written for the Neon-era production database; they are disabled and fail closed, and no
  Production migration, seeding, or data-sync path is approved yet. Protected scripts read
  `DEPLOYMENT_ENV`, never `APP_ENV`, because Staging also runs `APP_ENV=production`. See
  [deployment.md](deployment.md#protected-database-commands-phase-0-quarantine) and
  [ADR 011](../adr/011-three-environment-architecture.md).

## Migrations and the single-runner lock

`backend/api/scripts/migrate.py` applies Alembic to `head` without starting the API:

```bash
DEPLOYMENT_ENV=development uv run --project backend/api \
  python backend/api/scripts/migrate.py
```

- It uses `DatabaseSettings` and never instantiates the full application settings.
- It never calls `create_all` and never creates a migration revision.
- On PostgreSQL it takes a **session-level** advisory lock from `app/core/migration_lock.py` and
  passes the same connection to Alembic through `config.attributes["connection"]`. The lock covers
  the entire upgrade, is released on success or failure, and is also released by PostgreSQL when
  the connection closes after a crash.
- The lock key is fixed and documented: `int.from_bytes(b"charsooq", "big")`.
- If another runner holds the lock, the command waits up to
  `MIGRATION_LOCK_TIMEOUT_SECONDS` (default 60) and then exits non-zero with a clear timeout.
  Output is redacted: the database URL and password are never printed.
- A plain `alembic upgrade head` takes the same lock when it opens its own connection. A caller
  that supplies a connection (the standalone runner) gets that connection reused by Alembic.
- SQLite keeps the old no-lock behavior for Development. An explicitly identified Production
  deployment on a non-PostgreSQL dialect fails closed instead of running unprotected.

The API lifespan uses the same `apply_migrations()` path when `RUN_MIGRATIONS_ON_STARTUP` is true
(Development and Staging default; Production does not). Owner bootstrap is a separate switch
(`RUN_OWNER_BOOTSTRAP_ON_STARTUP`); the explicit `scripts/bootstrap_owner.py` command requires the
`admins` table to exist, does not create tables, and is idempotent. Production order is migration
runner → verify success → optional explicit owner bootstrap → API with both startup flags `false`
→ health/readiness. The API must never start before the schema is at `head`.
