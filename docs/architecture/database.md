# Database — چهارسوق

PostgreSQL 18 (Production pins `postgres:18.6-trixie`) + SQLAlchemy 2.x (`Mapped`/`mapped_column`) + Alembic (`backend/api/alembic.ini`, `backend/api/migrations/env.py`).

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

| Environment | Database                                                               |
| ----------- | ---------------------------------------------------------------------- |
| Development | Local PostgreSQL 18 (compose, host `:5433`)                            |
| Staging     | Neon                                                                   |
| Production  | PostgreSQL 18.6 container on `market-linux` (`compose.production.yml`) |

- Migrations run only against the database of the environment being deployed.
- The API engine reads only `DATABASE_URL` through `DatabaseSettings` (the application role).
  Alembic and `scripts/migrate.py` read only `MIGRATION_DATABASE_URL` through `MigrationSettings`
  (the migration role). `alembic.ini` deliberately contains no database URL, and the full
  application `Settings` is not required for migrations. When `MIGRATION_DATABASE_URL` is unset,
  Development/Staging fall back to `DATABASE_URL`; Production requires the dedicated value.
- `APP_ENV=production` requires an explicit, recognised `DEPLOYMENT_ENV`; a missing or unknown
  identity fails before any connection is opened, including in Alembic and offline SQL generation.
- When `DEPLOYMENT_ENV=production` is explicit, both URLs must be PostgreSQL with an explicit,
  non-loopback host and must use different roles. A missing URL, the committed localhost
  development default, SQLite, `localhost`, `127.0.0.0/8`, `::1`, and IPv4-mapped loopback
  addresses all fail before any connection is opened. Errors never include a URL, host, or
  credential. Development and Staging keep their previous compatibility.
- `RUN_MIGRATIONS_ON_STARTUP` defaults to `true` in Development/Staging and `false` in Production.
  Staging keeps automatic migrations; Production rejects an explicit `true` and uses the
  standalone runner.
- `RUN_OWNER_BOOTSTRAP_ON_STARTUP` follows the same defaults. Production rejects an explicit
  `true` and runs `scripts/bootstrap_owner.py` explicitly after migrations.
- Production migrations are ordered before the new API version and use a single locked runner;
  `compose.production.yml` makes `api` depend on the one-shot `migrate` service completing
  successfully. The runner uses only the `migration_database_url` secret and
  `DEPLOYMENT_ENV=production`; the API uses only `database_url`.
- No automatic Production → Staging/Development data transfer is allowed. Real data used outside
  Production requires a controlled, sanitized process.
- The existing dev-to-staging sync script is an explicit manual helper. The legacy `*-prod` targets
  were written for the Neon-era production database; they are disabled and fail closed, and no
  Production migration, seeding, or data-sync path is approved yet. Protected scripts read
  `DEPLOYMENT_ENV`, never `APP_ENV`, because Staging also runs `APP_ENV=production`. See
  [deployment.md](deployment.md#protected-database-commands-phase-0-quarantine) and
  [ADR 011](../adr/011-three-environment-architecture.md).

## Production container and storage

Production uses the pinned `postgres:18.6-trixie` image with no published host port. The database is
reachable only on the internal `backend` Compose network.

- **Volume path:** PostgreSQL 18 changed `PGDATA` to `/var/lib/postgresql/18/docker` and the
  official image declares the volume at `/var/lib/postgresql`. The Compose volume
  `charsooq-production_pgdata` is mounted at `/var/lib/postgresql`, not the old
  `/var/lib/postgresql/data` path.
- **Password:** the database container reads `POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password`
  (Docker Compose file-backed secret). The file must be readable by the image's `postgres` user
  (UID/GID `999:999`). No password is present in Compose or the image.
- **Data safety:** `make prod-down` runs `docker compose down` without `-v`; the volume and data stay
  in place. No default target deletes the volume.
- **Healthcheck:** `pg_isready -U charsooq -d charsooq -h 127.0.0.1`; `migrate` and `api` wait for it.
- **Backups:** the design and isolated rehearsal are in
  [backup-and-recovery.md](../operations/backup-and-recovery.md); scheduling, encryption/key custody,
  off-host storage, retention, and PITR remain open. Take a verified backup before destructive
  migrations.

### Roles and least privilege (implemented)

Production uses three independent roles. The names below are the documented convention; the actual
role names are read from the two database URLs, so an operator may choose different lowercase names
as long as both URLs point at the same database and use different roles.

| Role           | URL / credential                      | Rights                                                                                                                                                                                                                                                                           |
| -------------- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Administrative | `POSTGRES_USER` + `postgres_password` | `SUPERUSER`. Used only by the PostgreSQL container and the one-shot `provision` service. Never given to the API or migration runner.                                                                                                                                             |
| Migration      | `migration_database_url`              | `LOGIN`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOBYPASSRLS`; owns schema `public` and the objects Alembic creates; `CREATE` on the database for future trusted extensions.                                                                                               |
| Application    | `database_url`                        | `LOGIN`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOBYPASSRLS`; `CONNECT`; schema `USAGE`; `SELECT`/`INSERT`/`UPDATE`/`DELETE` on application tables; `USAGE`/`SELECT` on sequences. No `CREATE` on the schema, no object ownership, no role membership in the other roles. |

The committed migrations create every table in `public` (there is no `schema=` anywhere under
`backend/api/migrations`), so `public` is the target schema. The migration role owns it after
provisioning. `alembic_version` is explicitly excluded from the application grants, so the runtime
role cannot rewrite the recorded schema version. Future tables and sequences created by the
migration role receive the same application DML privileges through `ALTER DEFAULT PRIVILEGES`.

`app/core/provisioning.py` implements provisioning as a single transaction:

1. connect as the administrative role;
2. take a provisioning-specific advisory lock;
3. create or `ALTER` both roles with safe attributes and the passwords from the two URLs;
4. revoke role memberships and broad database/schema grants;
5. transfer existing objects owned by the administrative role (an old single-role volume) to the
   migration role;
6. ensure `alembic_version` exists, grant exact application DML/sequence privileges and default
   privileges, then revoke all privileges on `alembic_version` from the application role;
7. verify the post-state (no superuser/createdb/createrole/bypassrls, no schema `CREATE`, no role
   membership, migration role owns the schema, application role owns no objects) and raise if it
   does not match.

The `provision` service runs on every stack start and is idempotent. PostgreSQL initialization
scripts are **not** used for this: they run only when the data directory is first created, so they
cannot create, rotate, or repair roles on an existing volume. A pre-split volume is handled by the
ownership-transfer step above; no human `ALTER TABLE` loop is required.

Passwords come from `database_url`, `migration_database_url`, and `postgres_password` secret files.
They are never passed as command arguments, written to Compose, or printed. The provisioning module
does not log SQL and sets `log_statement=none` for its transaction so a server that logs statements
does not capture the `ALTER ROLE ... PASSWORD` text.

**Password rotation.** For the application and migration roles, change the password inside the role's
URL secret, then run `make prod-provision` (or let the next `make prod-up` run the `provision`
service), then restart the service that uses it (`api` for `database_url`, `migrate` for
`migration_database_url`). Rotation is a short window: the old credential keeps working until the
provisioning transaction commits, and the new credential works immediately afterwards.

The administrative role is different: `POSTGRES_PASSWORD_FILE` is read only when the image initializes
an empty data directory, so changing `postgres_password` and restarting does not rotate it. Use the
`psql \password` procedure in the
[Production runbook](../operations/production-runbook.md#94-administrative-postgresql-password-rotation),
verify the new credential over TCP, then replace the secret file.

**Migrating an existing single-role volume.** Take a verified backup, write
`migration_database_url` with the migration role/password, replace `database_url` with the
application role URL (same database host/name), then run `make prod-provision` followed by
`make prod-migrate` before recreating `api`. The old administrative role is untouched and remains
the container administrator; the provisioning step only transfers table/sequence/view ownership
from it to the migration role and grants the application role. If an object is owned by an
unexpected role, provisioning fails closed instead of changing it.

## Migrations and the single-runner lock

`backend/api/scripts/migrate.py` applies Alembic to `head` without starting the API:

```bash
DEPLOYMENT_ENV=development uv run --project backend/api \
  python backend/api/scripts/migrate.py
```

- It uses `MigrationSettings` (`MIGRATION_DATABASE_URL`) and never instantiates the full application
  settings or reads the API's application credential in Production.
- It never calls `create_all` and never creates a migration revision.
- On PostgreSQL it takes a **session-level** advisory lock from `app/core/migration_lock.py` and
  passes the same connection to Alembic through `config.attributes["connection"]`. The lock covers
  the entire upgrade, is released on success or failure, and is also released by PostgreSQL when
  the connection closes after a crash.
- The lock query opens a SQLAlchemy transaction before Alembic configures itself. Alembic does not
  commit a transaction it did not start, so `migrations/env.py` commits the connection after the
  upgrade; otherwise closing the connection would roll the migrations back.
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
