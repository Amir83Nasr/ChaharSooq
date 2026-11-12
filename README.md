# چهارسوق (Charsooq)

Persian, RTL-first admin web application. Monorepo: Next.js frontend + FastAPI backend + PostgreSQL.

Three independent environments: Development (local), Staging (Vercel + FastAPI Cloud + Neon), and Production (Docker Compose on `market-linux`). See [docs/architecture/deployment.md](docs/architecture/deployment.md).

## Tech stack

- Frontend: Next.js 16, React 19, TypeScript (strict), Tailwind CSS 4, shadcn/ui, pnpm
- Backend: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, uv
- Database: PostgreSQL (Production pins `postgres:18.6-trixie`)

See [docs/architecture/overview.md](docs/architecture/overview.md) for architecture and [AGENTS.md](AGENTS.md) for agent rules.

## Requirements

- Node.js 22, pnpm 11
- Python >= 3.12, uv
- Docker (dev postgres) or local PostgreSQL

## Installation

```bash
make install                  # pnpm install, uv sync --locked, git hooks (Lefthook)
cp backend/api/.env.example backend/api/.env.local
cp apps/web/.env.example apps/web/.env.local
```

## Development commands

Run everything from the repository root with make (`make help` lists all targets):

```bash
make install           # install frontend + backend deps
make db-up             # start dev postgres (compose, host :5433)
make db-migrate        # apply Alembic migrations to dev database
make db-seed           # ensure the env-managed owner (OWNER_USERNAME/OWNER_PASSWORD)
make db-seed-parsina   # upsert data/parsina.csv into the dev catalog (keeps links)
make db-seed-demo      # add demo competitor prices, daily changes, weights and price bounds
make dev-all           # postgres + migrate, then backend :8000 + frontend :3000
```

Individual servers:

```bash
make dev-api    # backend API with reload (:8000, expects postgres up)
make dev-web    # frontend only (turbo)
```

Checks, tests, build:

```bash
make lint       # frontend lint + backend ruff check/format
make typecheck  # frontend tsc + backend pyright
make test       # ui vitest + backend pytest
make check      # lint + typecheck + test
make build      # production build (web)
make clean-cache # remove regenerable tool caches (.turbo, .ruff_cache, …)
make clean-build # remove build output and test artifacts (.next, …)
```

Without make:

```bash
pnpm lint         # frontend lint
pnpm typecheck    # frontend typecheck
pnpm format       # frontend format (writes)
pnpm format:check # frontend format check
pnpm test         # frontend unit tests
pnpm --filter web build            # production build

uv run --project backend/api ruff check .          # backend lint
uv run --project backend/api ruff format --check . # backend format check
uv run --project backend/api pyright               # backend typecheck
cd backend/api && uv run --no-sync pytest -q       # backend tests (reads pyproject)
```

Caches are regenerable and gitignored. Ruff and pytest place their cache next to the
directory you run them from, so running the backend commands from the repository root
also leaves a `.ruff_cache` / `.pytest_cache` there. `make clean-cache` removes every
cache copy; `make clean-build` removes `.next` and Playwright artifacts.

## Environment variables

Each app owns its env file: [backend/api/.env.example](backend/api/.env.example) (copy to `backend/api/.env.local`) and [apps/web/.env.example](apps/web/.env.example) (copy to `apps/web/.env.local`). Never commit real secrets. Values are environment-specific: never share secrets or `DATABASE_URL` between Development, Staging, and Production. Deployed environments get their variables from their own platform or server secret source, not from env files shipped with the repository. The backend reads its env file by absolute path, so every backend process resolves the same configuration sources. In Production the API and Alembic intentionally use different credentials (`DATABASE_URL` and `MIGRATION_DATABASE_URL`) for the same database. A shared root `.env.local` (or `.env`) is also loaded by both apps as a fallback, which is convenient for LAN/mobile dev (e.g. whitelisting device IPs in `ALLOWED_DEV_ORIGINS` / `CORS_ORIGINS`); per-app values take precedence.

| Variable                         | Purpose                                                                                                                                                                                                                                                                                                                                           |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `APP_ENV`                        | `development` / `test` / `production`. Staging and Production both run `production` app behavior (Secure cookies, strict secret checks); the environment is identified by the explicit `DEPLOYMENT_ENV`.                                                                                                                                          |
| `DEPLOYMENT_ENV`                 | Explicit environment identity: `development`, `staging`, `production`. Mandatory whenever `APP_ENV=production`; a missing or unknown value fails configuration before any database connection. It also gates protected scripts (the Development/Staging Make targets set it). `APP_ENV` cannot replace it because Staging also uses `production`. |
| `DATABASE_URL`                   | The **application role** SQLAlchemy URL, e.g. `postgresql+psycopg://charsooq_app:<password>@localhost:5433/charsooq`. The API reads only this URL; it is never used for migrations in Production. In an explicitly identified Production deployment it must be PostgreSQL and must not target localhost or any loopback address.                  |
| `MIGRATION_DATABASE_URL`         | The **migration role** SQLAlchemy URL used only by Alembic and `scripts/migrate.py`. Required in Production and must use a different PostgreSQL role than `DATABASE_URL`. Development/Staging fall back to `DATABASE_URL` when it is unset.                                                                                                       |
| `SECRETS_DIR`                    | Optional directory of one-value secret files: `database_url`, `migration_database_url`, `postgres_password`, `session_secret`, `owner_password`, `parsina_password`. Environment variables take precedence; the Production stack mounts it at `/run/secrets`.                                                                                     |
| `SESSION_SECRET`                 | Validated in production (minimum 32 bytes); the current opaque-token sessions do not sign cookies with it                                                                                                                                                                                                                                         |
| `SESSION_SAMESITE`               | `lax` (same-site dev) / `none` (split frontend/API hosts, e.g. Staging)                                                                                                                                                                                                                                                                           |
| `RUN_MIGRATIONS_ON_STARTUP`      | Defaults: `true` in Development/Staging, `false` in Production. `true` runs Alembic in the API lifespan under the advisory lock; Production rejects an explicit `true` so the standalone migration runner must apply schema first.                                                                                                                |
| `RUN_OWNER_BOOTSTRAP_ON_STARTUP` | Defaults: `true` in Development/Staging, `false` in Production. `true` ensures the env-managed owner in the API lifespan; Production rejects an explicit `true` so `bootstrap_owner.py` is the explicit step (independent of migrations).                                                                                                         |
| `MIGRATION_LOCK_TIMEOUT_SECONDS` | Seconds to wait for the PostgreSQL migration advisory lock (default `60`, `0` fails immediately). Applies to startup migrations and the standalone runner                                                                                                                                                                                         |
| `API_URL_INTERNAL`               | Server-side API origin for Next `/api/*` rewrites; falls back to `NEXT_PUBLIC_API_URL`                                                                                                                                                                                                                                                            |
| `NEXT_PUBLIC_API_URL`            | API origin fallback for rewrites (browser always calls same-origin `/api/*`)                                                                                                                                                                                                                                                                      |
| `CORS_ORIGINS`                   | Backend CORS allowlist, comma-separated                                                                                                                                                                                                                                                                                                           |
| `ALLOWED_DEV_ORIGINS`            | Extra Next.js dev origins, comma-separated                                                                                                                                                                                                                                                                                                        |
| `OWNER_USERNAME`                 | Highest-privilege `owner` login. Defaults to `superadmin`. The API creates this account on boot unless `RUN_OWNER_BOOTSTRAP_ON_STARTUP=false`; `bootstrap_owner.py` is the explicit path.                                                                                                                                                         |
| `OWNER_PASSWORD`                 | Owner password. Required in production (minimum 8 characters). Changing it re-hashes the account and revokes its sessions on the next boot or explicit owner bootstrap.                                                                                                                                                                           |
| `PARSINA_*`                      | Parsina accounting API (URL, credentials, org, year, optional warehouse/sale-type). Empty = integration off. `PARSINA_SYNC_INTERVAL_MINUTES` (default 1440) seeds the initial auto-sync interval and `PARSINA_SYNC_ENABLED` toggles the backend scheduler                                                                                         |
| `PRODUCTS_CSV_PATH`              | Development-only product CSV; defaults to `<repo>/data/parsina.csv`                                                                                                                                                                                                                                                                               |

### Environment examples

`APP_ENV=production` is application behavior, not environment identity: Staging and Production
both use it. When it is set, an explicit `DEPLOYMENT_ENV` is mandatory and an unknown value fails
configuration before the database is opened. Development keeps the previous lenient behavior.

```bash
# Development (local)
APP_ENV=development
DEPLOYMENT_ENV=development          # optional for the API, required by protected CLIs
DATABASE_URL=postgresql+psycopg://charsooq:charsooq@localhost:5433/charsooq
# MIGRATION_DATABASE_URL is optional here: migrations fall back to DATABASE_URL.
RUN_MIGRATIONS_ON_STARTUP=true
RUN_OWNER_BOOTSTRAP_ON_STARTUP=true

# Staging (production behavior, staging identity)
APP_ENV=production
DEPLOYMENT_ENV=staging
DATABASE_URL=<staging application-role PostgreSQL URL>
# Optional in Staging: migrations fall back to DATABASE_URL.
RUN_MIGRATIONS_ON_STARTUP=true
RUN_OWNER_BOOTSTRAP_ON_STARTUP=true

# Production (explicit identity; startup steps are separate commands)
APP_ENV=production
DEPLOYMENT_ENV=production
DATABASE_URL=<production application-role URL, not localhost/loopback>
MIGRATION_DATABASE_URL=<production migration-role URL, different role>
RUN_MIGRATIONS_ON_STARTUP=false
RUN_OWNER_BOOTSTRAP_ON_STARTUP=false
```

Production rejects a non-PostgreSQL URL, a URL without a host, and any `localhost` or loopback
host (`127.0.0.0/8`, `::1`, IPv4-mapped loopback). The error never prints the URL, host, or
credentials. Explicitly enabling either startup step in Production is also rejected; use the
ordered commands in [Migrations](#migrations) instead. Values shown above are placeholders, not
secrets.

## Roles and users

Accounts have one of three roles:

| Role     | Can do                                                                                             |
| -------- | -------------------------------------------------------------------------------------------------- |
| `owner`  | Everything, including creating/removing admins. Comes only from `OWNER_USERNAME`/`OWNER_PASSWORD`. |
| `admin`  | Shop data (products, categories, settings, sync) and viewer management. Never sees other admins.   |
| `viewer` | Read-only: catalog, dashboard, integration pages, and the settings values those views use.         |

`/users` is available to the owner and admins. The owner sees every account and may create or delete `admin` and `viewer` accounts. An admin sees viewer accounts plus their own account and may create/delete viewers; the owner and other admins stay hidden. At least one management account always remains; since the owner cannot be deleted, the owner can remove every admin. Viewers get `403 forbidden` on every write. `/settings` is available to the owner and admins; the sidebar hides the سیستم group from viewers. See [docs/architecture/authentication.md](docs/architecture/authentication.md) and [ADR 010](docs/adr/010-owner-role.md).

```bash
GET    /api/v1/users          # owner: all accounts; admin: viewers + self
POST   /api/v1/users          # { "username", "password", "role": "admin" | "viewer" }
DELETE /api/v1/users/{id}     # also revokes that account's sessions
```

## Product data sources

Products mirror an external catalog (`external_id` = Parsina `goodId`), and the GET endpoints always read the local mirror. Where the mirror comes from depends on `APP_ENV`:

- **production** — live Parsina API (`PARSINA_*` credentials). The backend scheduler syncs at the interval configured in Settings (default `PARSINA_SYNC_INTERVAL_MINUTES`, 1440); the products page has a «به‌روزرسانی از پارسینا» button for a manual run.
- **development** — `data/parsina.csv` (an export of the live catalog, same field names). `make db-seed-parsina` upserts it into the dev product mirror; existing product ids, categories, and competitor links are kept and rows missing from the CSV are deactivated, never deleted. The same button re-imports the file. No Parsina credentials are needed; the scheduler ticks on the same interval from the CSV, like production. The export only carries `countUnit` ids, so the CSV source supplies mock unit titles to keep the dev catalog identical to production. `make db-seed-demo` additionally gives every active product demo competitor prices (Digikala/Technolife for appliances, Sofa for furniture, DigiFresh for carpets) with two daily observations, the missing suggested-price weights, and demo floor/ceiling percentages, so all products-table columns are populated in dev. Demo bounds rotate through four clamp scenarios — below the floor, above the ceiling, inside the bounds, and no bounds — so the suggested-price clamp is visible in the table; only bounds the seed itself wrote are refreshed, while an admin's saved clamp is kept. The rotation is keyed on the synced product identity (`external_id`, or SKU for manual rows), so dev and staging show the same demo prices and bounds even though the two databases assign different ids. Demo links use a `demo-` URL path; re-running refreshes only those rows and never touches real/manual links.

Both paths share one validation/apply routine and one DB lock, so runs never overlap. Manual runs return `202` and the UI polls `GET /integrations/parsina/status` until the run finishes, then re-fetches the table in place. A failed or partial fetch never overwrites the last successful data; rows missing from a complete listing are deactivated, never deleted.

## Competitor prices

Competitor links and observations are stored separately from the Parsina catalog. In product details, admins can add Digikala, Technolife, or another public product URL; run a check; save a manual price/stock correction; disable the link; or delete it. Each product dialog also has a «به‌روزرسانی همه قیمت‌ها» button that re-checks all of its active links at once, and the products header has a «به‌روزرسانی قیمت رقبا» button that refreshes every active link in the background (poll `GET /integrations/competitors/status`, `409` while a run holds the lock). The same bulk refresh also runs automatically on a schedule set in Settings («فاصله به‌روزرسانی خودکار قیمت رقبا», default 24 hours). Automatic extraction is limited to Digikala and Technolife public product pages, uses JSON-LD product offers only, checks each host's `robots.txt`, validates redirects and public DNS, and stops for six hours after a `403` or `429`. Unknown stores remain manual-only. Prices expire after 24 hours by default and stale values are excluded from the table and competitor-price filters. Configure `COMPETITOR_REQUEST_INTERVAL_SECONDS` (default 5) and `COMPETITOR_PRICE_TTL_HOURS` (default 24) in `backend/api/.env.local`.

## Database setup

Development commands (the Make targets set `DEPLOYMENT_ENV=development` for the scripts):

```bash
make db-migrate        # dev: start postgres + locked standalone migration runner
make db-bootstrap-owner # ensure the owner via the explicit no-create_all CLI
make db-seed            # ensure the owner account from OWNER_USERNAME/OWNER_PASSWORD
make db-seed-parsina    # upsert dev product catalog from data/parsina.csv
make db-seed-demo       # demo competitor prices + daily changes for the products table
make db-clear-products  # delete all products + competitor links (development only)
```

Staging helpers (they set `DEPLOYMENT_ENV=staging` and read `backend/api/.env.staging`):

```bash
make db-sync-dev-to-staging # upsert dev data into staging Neon + demo competitor prices
make db-seed-demo-staging   # only refresh staging demo competitor prices
```

Protected scripts read `DEPLOYMENT_ENV`, not `APP_ENV`: Staging and Production both run
`APP_ENV=production`, so `APP_ENV` cannot identify the target. A missing or unrecognised
`DEPLOYMENT_ENV`, or an environment the script does not allow, makes it exit non-zero before it
reads `DATABASE_URL` or opens a connection. Running a script directly therefore needs the identity:

```bash
DEPLOYMENT_ENV=development uv run --project backend/api python backend/api/scripts/migrate.py
DEPLOYMENT_ENV=development uv run --project backend/api python backend/api/scripts/bootstrap_owner.py
DEPLOYMENT_ENV=development uv run --project backend/api python backend/api/scripts/seed_admin.py
```

`migrate.py` and `bootstrap_owner.py` accept all three identities because they are the explicit
paths a controlled deployment can use. `seed_admin.py` stays Development/Staging only: it also
runs `create_all` and predates the separated owner CLI.

The Neon-era production targets are disabled and fail closed with migration guidance:
`make db-migrate-prod`, `make db-seed-prod`, `make db-sync-dev-to-prod`, plus the
`make sync-prod` / `make dev-to-prod` aliases. No Production deployment workflow is approved yet;
the locked standalone migration runner and explicit owner CLI are the building blocks it must use.
See [docs/architecture/deployment.md](docs/architecture/deployment.md).

## Migrations

Schema changes require an Alembic migration under `backend/api/migrations/`. Autogenerate from models, review, then apply (`make db-migrate`).

- Migration is now a separate, controlled step: `backend/api/scripts/migrate.py` applies `head` under a PostgreSQL session-level advisory lock. The API lifespan runs the same locked path by default only in Development and Staging (`RUN_MIGRATIONS_ON_STARTUP=true`); Production defaults it to `false`.
- Migrations read `MIGRATION_DATABASE_URL` only. In Production it is mandatory and must use the migration role; the API's `DATABASE_URL` (application role) is never accepted as a migration credential. Development and Staging fall back to `DATABASE_URL` when the dedicated value is unset, preserving the previous single-URL behavior.
- A plain `alembic upgrade head` also takes the same lock. The lock and the Alembic upgrade share one connection, so they cannot drift onto different sessions.
- The lock key is fixed and documented (`app/core/migration_lock.py`, ASCII `charsooq`). A second runner waits up to `MIGRATION_LOCK_TIMEOUT_SECONDS` (default 60), then fails with a clear timeout instead of racing. On success or failure the lock is released; closing the connection or killing the process is the final PostgreSQL-side safety net.
- PostgreSQL is required for the lock. SQLite keeps the previous development behavior; an explicitly identified Production deployment fails closed if the URL is not PostgreSQL or targets a loopback host.
- The standalone runner never calls `create_all`, never creates a revision, and never prints the database URL or a password. A failed migration or lock timeout exits non-zero.
- `RUN_MIGRATIONS_ON_STARTUP=false` skips only the lifespan migration. `RUN_OWNER_BOOTSTRAP_ON_STARTUP=false` skips only the env-managed owner; the two switches are independent. Production defaults both to `false` and rejects an explicit `true`.
- The env owner can also be ensured explicitly after the schema is ready: `python backend/api/scripts/bootstrap_owner.py`. It never creates tables, is idempotent, and keeps the single-owner invariant. Production must use this explicit path with the startup flag `false`.
- Production order is fixed: secrets/configuration → database reachability → `scripts/migrate.py` → verify the migration succeeded → explicit `scripts/bootstrap_owner.py` when owner provisioning is needed → start the API with both startup flags `false` → check `/health` and `/ready`. Never start the API before the schema is at `head`.
- CI proves it: fresh `upgrade head`, idempotent re-upgrade, single-head assertion, `alembic check` drift detection, and a downgrade/upgrade round-trip.
- `make db-validate` runs the offline part locally (no database needed); `make check` includes it.
- `make db-migrate-prod` is disabled: the Neon-era path is not approved for Production. Production deployments must use the standalone runner as the ordered pre-start step described in [docs/architecture/deployment.md](docs/architecture/deployment.md).

## API contract

Base path `/api/v1`. Interactive docs: Swagger UI at `/docs` (start the API with `make dev-api` or `make dev-all`, then open <http://localhost:8000/docs>) and ReDoc at `/redoc`. Log in through `POST /api/v1/auth/login`; the browser sends the resulting HttpOnly cookie automatically. Committed OpenAPI snapshot: [backend/api/openapi.json](backend/api/openapi.json) — regenerate after any route/schema change:

```bash
uv run --project backend/api python backend/api/scripts/export_openapi.py
```

The frontend client (`apps/web/lib/api.ts`) mirrors these shapes; see [docs/api/README.md](docs/api/README.md).

## Testing

- Frontend unit tests: `packages/ui/src/lib/*.test.ts` (vitest) — Persian digits, `٬` grouping, `٫` dates
- Frontend e2e: `apps/web/e2e/` (playwright) — unauthenticated redirects, Persian login form, RTL shell, mobile layout; runs against the production build without a backend — `pnpm --filter web test:e2e`
- Backend tests: `backend/api/tests/` (pytest) — auth flow, roles and user management, product CRUD, validation envelope
- CI runs lint, format check, typecheck, both test suites, the production build, and the Playwright e2e suite. The repository has no deploy workflow: Staging deploys through the Vercel/FastAPI Cloud Git integration, and Production promotion is a separate explicit step.

## Build

```bash
make build
```

## Production Docker stack

Production uses a separate file, [compose.production.yml](compose.production.yml); it does not read
or extend [compose.yml](compose.yml). The stack is built for a Docker Engine host such as
`market-linux` but this repository does not deploy it and the stack is not live yet.

```bash
make prod-config    # validate compose structure; no secret files needed
make prod-build     # build pinned API + web production images
make prod-up        # start db -> provision -> migrate -> api -> web
make prod-provision # run idempotent role provisioning once (needs secrets)
make prod-migrate   # run the locked migration runner once (needs secrets)
make prod-ps        # service status and health
make prod-logs      # follow logs
make prod-down      # stop services; volumes and data are kept
```

`make prod-up` runs the one-shot `provision` and `migrate` services in order; the API is not
created until both succeed. `make prod-provision` and `make prod-migrate` run those same steps
manually as one-offs, and `make prod-bootstrap-owner` runs the explicit owner CLI. All of them need
real Production secrets; owner bootstrap remains a separate explicit step.

### Database roles and production secrets

Production separates three PostgreSQL roles. The image-created `charsooq` role is the
**administrative superuser** and is used only by PostgreSQL itself and the one-shot provisioning
service. `charsooq_migrator` owns the schema and runs Alembic; `charsooq_app` is the runtime role
with `CONNECT`, schema `USAGE`, and `SELECT`/`INSERT`/`UPDATE`/`DELETE` on application tables and
`USAGE`/`SELECT` on sequences. The application role cannot create, alter, or drop schema objects and
cannot create roles. Role names are read from the URLs, so an operator may choose different
lowercase names; both URLs must target the same database.

Secrets are file-backed Docker Compose secrets, sourced from outside the repository. The default
host directory is `/etc/charsooq/secrets`; override it with `CHARSOOQ_SECRETS_DIR=...`.

| Secret file              | Used by                | Content                                                              |
| ------------------------ | ---------------------- | -------------------------------------------------------------------- |
| `postgres_password`      | `db`, `provision`      | Password for the administrative `charsooq` role                      |
| `database_url`           | `provision`, `api`     | `postgresql+psycopg://charsooq_app:<password>@db:5432/charsooq`      |
| `migration_database_url` | `provision`, `migrate` | `postgresql+psycopg://charsooq_migrator:<password>@db:5432/charsooq` |
| `session_secret`         | `api`                  | Session configuration secret, at least 32 bytes                      |
| `owner_password`         | `api`                  | Owner bootstrap password, at least 8 characters                      |
| `parsina_password`       | `api`                  | Parsina password when the integration is configured                  |

The API never receives `postgres_password` or `migration_database_url`; the migration runner never
receives `postgres_password` or `database_url`. The provisioning service receives only the three
secrets it needs to create roles and set passwords.

Compose file-backed secrets are bind-mounted read-only into `/run/secrets`; host ownership and mode
are what the container sees. `uid`, `gid`, and `mode` in the Compose file only apply to Swarm
secrets and are intentionally not set. Make `postgres_password` owned by `999:999` with mode `0440`
(the `provision` service joins GID `999` to read it), and the other files owned by `10001:10001`
with mode `0400`. Never commit these files or place them in an image.
See [docs/architecture/deployment.md](docs/architecture/deployment.md#production-secrets) for the
exact commands, rotation steps, and verification.

No host port is published by this stack. `db`, `provision`, `migrate`, `api`, and `web` listen only on
internal Compose networks (`web:3000`, `api:8000`, `db:5432`). TLS termination and the reverse proxy
are a separate task; backup tooling and restore drills are not implemented yet. PostgreSQL data
lives in the `charsooq-production_pgdata` volume at `/var/lib/postgresql` (the PostgreSQL 18 image
path), and `make prod-down` never removes it.

## Deployment

Charsooq has three independent environments — Development, Staging, and Production. Each has its own secrets, database credentials (`DATABASE_URL`, plus `MIGRATION_DATABASE_URL` where role separation is used), and configuration; no Production data is copied automatically to Staging or Development. A push to `main` is not a Production release. See [docs/architecture/deployment.md](docs/architecture/deployment.md) for the source of truth.

- Development: local Next.js + FastAPI + PostgreSQL; `make docker-up` runs `web` + `api` + `postgres` from [compose.yml](compose.yml), with a one-shot `migrate` service running the locked migration runner before the API starts. The development stack sets `APP_ENV=production` to exercise production behavior locally and `DEPLOYMENT_ENV=development` so it is never mistaken for Production. `compose.yml` is the development stack, not a Production file.
- Staging: Vercel frontend (`vercel.json` pins pnpm install/build for the monorepo) + FastAPI Cloud backend (`make deploy-api`) + Neon database. Set `API_URL_INTERNAL` + `NEXT_PUBLIC_API_URL` to the Staging API origin in Vercel — the build fails fast if they still point at localhost. Browser calls same-origin `/api/*`; Next rewrites to the API origin, so the session cookie stays first-party. The API auto-migrates on boot in Staging.
- Production: Docker Engine + Docker Compose on Ubuntu `market-linux` (`172.30.2.2`): Next.js, FastAPI, and PostgreSQL 18.6, with separate administrative, migration, and application database roles. [compose.production.yml](compose.production.yml) encodes the service order (`db` → `provision` → `migrate` → `api` → `web`), file-backed secrets, internal networks, and health checks. TLS/reverse proxy, backups, image registry/promotion, and the actual server deployment remain separate open work. Production is not live yet; see the deployment document.
