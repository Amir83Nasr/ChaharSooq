# Backend — چهارسوق

FastAPI service in `backend/api`. Entry point: `app.main:app`; `create_app()` wires middleware,
exception handlers, routers, and the scheduler. Schema changes live in `migrations/` (Alembic).

## Layers

```text
app/api/routes  →  app/services  →  app/repositories  →  app/core/database  →  PostgreSQL
```

| Layer              | Responsibility                                                                               |
| ------------------ | -------------------------------------------------------------------------------------------- |
| `api/routes`       | Parse input, call one service, set status codes. No business logic, no SQL.                  |
| `api/dependencies` | DB sessions (`get_db`, `get_db_readonly`) and auth guards (`require_user`, `require_admin`). |
| `api/openapi.py`   | Tag metadata, descriptions, and shared error responses for Swagger.                          |
| `services`         | Business rules; the only layer that coordinates multiple repositories.                       |
| `repositories`     | All SQLAlchemy 2.x queries. ORM models never leave this layer.                               |
| `schemas`          | Pydantic boundary types for requests and responses.                                          |
| `models`           | SQLAlchemy ORM models.                                                                       |
| `integrations`     | External systems: Parsina, the dev mirror, the CSV fixture, competitor pages.                |
| `core`             | Config, engine/session, security, rate limiting, migrations, scheduler, errors.              |

Shared `__init__.py` files re-export the public names, so handlers import from the package
(`from app.services import ProductService`). Standalone ops scripts live in `scripts/`;
`common.py` holds their shared session/env helpers.

## Request lifecycle

1. Middleware adds security headers and CORS, and rate-limits `POST /auth/login`.
2. The route validates input through a schema, resolves the session cookie through
   `require_user` (reads) or `require_admin` (writes), and calls exactly one service.
3. The service applies the rules and delegates persistence to repositories.
4. Read handlers use a read-only session; write handlers use a committing session.
5. Exceptions become the shared error envelope. Validation errors are translated to Persian
   field messages; unmatched routes and HTTP errors never leak Starlette's English defaults.
6. The response is serialized from the declared Pydantic model.

Tests create the app through the same factory, so middleware and handlers stay covered.

## Modules

| Domain       | Routes                                         | Services / repositories                             | Schemas                         |
| ------------ | ---------------------------------------------- | --------------------------------------------------- | ------------------------------- |
| Auth         | `auth.py`                                      | `auth`                                              | `auth`                          |
| Catalog      | `products.py`, `categories.py`, `dashboard.py` | `products`, `catalog`, `dashboard`                  | `catalog`, `dashboard`          |
| Competitors  | `competitors.py`                               | `competitor`, `competitor_check`, `competitor_sync` | `competitor`, `suggested_price` |
| Integrations | `integrations.py`                              | `sync`, `competitor_sync`                           | `catalog`, `competitor`         |
| Settings     | `settings.py`                                  | `settings`                                          | `settings`                      |
| Users        | `users.py`                                     | `users`                                             | `users`                         |
| Health       | `health.py`                                    | —                                                   | —                               |

## Authentication and security

- Passwords are hashed with Argon2id (`argon2-cffi`); plaintext is never stored or logged.
- Sessions are opaque random tokens; only their SHA-256 hash is stored with an expiry.
- Accounts have a `role`: `admin` manages everything; `viewer` is read-only. Read routes use
  `require_user`; write routes and `/api/v1/users*` use `require_admin` (`403 forbidden` otherwise).
- The session ID travels in an HttpOnly cookie (`charsooq_session`, configurable). `Secure` is on
  in production or when `SameSite=None`; the explicit policy is `SameSite=Lax` by default.
- Login rotates the session: a fresh login invalidates older sessions for that admin.
- Login is limited to 10 attempts per minute per IP and username. The limiter is in-memory by
  default and shared across replicas when `REDIS_URL` is set.
- Every response carries `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Content-Security-Policy: frame-ancestors 'none'`, and a restrictive `Permissions-Policy`;
  production adds HSTS.
- CORS uses an explicit origin allowlist and limited methods/headers.
- Configuration loads repo-root env files first, then `backend/api/.env*`; production fails fast
  when `SESSION_SECRET` is the dev default or shorter than 32 bytes.

See [authentication.md](authentication.md), [ADR 002](../adr/002-authentication.md), and
[ADR 009](../adr/009-role-based-access.md).

## Product data and sync

`ProductSyncService` handles the manual button and the scheduler through one path. The source is
chosen by environment in `app/integrations/sources.py`:

| `APP_ENV`     | Source                                                                       |
| ------------- | ---------------------------------------------------------------------------- |
| `production`  | Live Parsina API, or the dev database mirror when `DEV_DATABASE_URL` is set. |
| `development` | `data/parsina.csv` (a Parsina export, same field names).                     |
| `test`        | No scheduler; tests inject sources and transports.                           |

Rules shared by every source:

- Identity is Parsina `goodId`; re-runs update instead of duplicating.
- Nothing is written until the whole payload validates; a short/invalid listing is rejected and
  the previous data stays intact.
- A complete listing is authoritative: active rows missing from it are deactivated (soft delete),
  including manual rows. Runs never hard-delete products.
- Failures never overwrite `last_success_at`.
- A database lock per job admits one manual or scheduled run of that job at a time.

The scheduler starts in the lifespan for every environment except `test`. Its loop re-reads the
intervals each tick, so Settings changes apply without a process restart. `make db-seed-parsina`
loads the dev fixture and `make db-clear-products` empties it (development only). See
[ADR 006](../adr/006-dev-scheduler.md) and [ADR 005](../adr/005-dev-db-sync-simulation.md).

## Competitor prices

Links and observations are stored separately from the Parsina catalog. Digikala, Technolife,
Sofa Mobl, and DigiFresh product pages are fetched through JSON-LD offers; `other` stores are
manual-only. Sofa/DigiFresh are daily trackers: one observation per UTC day feeds
`price_change_percent`, which replaces the competitor price in the furniture/carpet suggested
formula. Fetched prices expire after `COMPETITOR_PRICE_TTL_HOURS` (default 24), and
`COMPETITOR_REQUEST_INTERVAL_SECONDS` (default 5) throttles requests. The fetcher checks
`robots.txt`, validates redirects and public DNS, and pauses the store for six hours after
`403`/`429`.

Admins can run one link, every link of a product, or a bulk refresh. Bulk runs use the same lock
model as the product sync and are also scheduled from Settings. Manual overrides take precedence
over fetched values (`effective_*` fields) and survive until cleared. See
[architecture/api.md](api.md#competitor-prices).

## Settings

Settings are key/value rows read through `SettingsService`, with validation at both the schema and
service layers: low-stock threshold, default page size, sync interval, competitor refresh interval,
default competitor store, per-section competitor weights for the suggested price, and the visible
product-table columns.

## OpenAPI and documentation

- `app/api/openapi.py` owns the tag list, app description, and shared `401/404/409/422/429/503`
  responses. Routers apply a tag and the shared `401` once.
- Each operation has a summary, description, and a stable `operationId` derived from the handler
  name; the session cookie is declared as an `apiKey` cookie scheme.
- `scripts/export_openapi.py` writes `backend/api/openapi.json`; `scripts/check_openapi_fresh.py`
  fails when it is stale (CI, `make check`, pre-commit). Never edit the snapshot by hand.
- Swagger UI is served at `/docs`, ReDoc at `/redoc`. Usage notes:
  [API contract](../api/README.md).

## Testing

```bash
uv run --project backend/api ruff check .
uv run --project backend/api ruff format --check .
uv run --project backend/api pyright          # strict
cd backend/api && uv run pytest -q            # coverage floor 80%
```

Tests mirror domains (`tests/test_auth.py`, `test_products.py`, `test_categories.py`,
`test_settings.py`, …) with an in-memory SQLite fixture; `tests/helpers.py` owns login/seed helpers.
PostgreSQL-only guards skip on SQLite and run in CI's Postgres job. `tests/test_openapi.py` keeps
the contract documented and the snapshot honest. See [testing.md](testing.md).
