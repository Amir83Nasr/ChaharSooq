# چهارسوق (Charsooq)

Persian, RTL-first admin web application. Monorepo: Next.js frontend + FastAPI backend + PostgreSQL.

Three independent environments: Development (local), Staging (Vercel + FastAPI Cloud + Neon), and Production (Docker Compose on `market-linux`). See [AGENTS.md](AGENTS.md) section 3.

## Tech stack

- Frontend: Next.js 16, React 19, TypeScript (strict), Tailwind CSS 4, shadcn/ui, pnpm
- Backend: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, uv
- Database: PostgreSQL (Production pins `postgres:19.0-trixie`; see [ADR 028](docs/adr/028-postgresql-19-upgrade-readiness.md))

See [AGENTS.md](AGENTS.md) for architecture and agent rules.

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

Run everything from the repository root with make. `make help` lists the short user
shortcuts below; `make help-all` lists every target.

```bash
make install           # install frontend + backend deps
make db-up             # start dev postgres (compose, host :5433)
make db-down           # stop dev postgres (data volume kept)
make db-migrate        # apply Alembic migrations to dev database
make db-seed           # ensure the env-managed owner (OWNER_USERNAME/OWNER_PASSWORD)
make db-seed-parsina   # upsert the saved Parsina export into the dev catalog (keeps links)
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
make format     # format frontend + backend source files in place
make lint       # frontend lint + backend ruff check/format
make typecheck  # frontend tsc + backend pyright
make test       # ui vitest + backend pytest
make check      # lint + typecheck + tests + offline migration and OpenAPI checks
make build      # production build (web)
make clean      # remove regenerable caches and build output
make clean-cache # remove regenerable tool caches (.turbo, .ruff_cache, …)
make clean-build # remove build output and test artifacts (.next, …)
```

On the server (or from a laptop with `SSH_HOST=...`), `make prod-deploy` reads the newest
published GitHub Release, resolves it to image digests, pulls them, provisions the
database, applies pending migrations, and verifies service and endpoint health. It
prints numbered progress and a final status summary. `make prod-logs` follows the logs
and accepts the same `SSH_HOST=...` option. Both are in the short `make help` list. See
[Deployment](#deployment) for the full flow.

Without make:

```bash
pnpm lint         # frontend lint
pnpm typecheck    # frontend typecheck
pnpm format       # frontend format (writes)
pnpm format:check # frontend format check
pnpm test         # frontend unit tests
pnpm --filter web build            # production build

RUFF_CACHE_DIR=backend/api/.ruff_cache uv run --project backend/api ruff check .          # backend lint
RUFF_CACHE_DIR=backend/api/.ruff_cache uv run --project backend/api ruff format --check . # backend format check
uv run --project backend/api pyright                                                     # backend typecheck
cd backend/api && uv run --no-sync pytest -q                                            # backend tests (reads pyproject)
```

Caches are regenerable and gitignored. `make lint` and the git hooks set
`RUFF_CACHE_DIR=backend/api/.ruff_cache` so Ruff keeps its cache under `backend/api/`
even when invoked from the repository root; use the same variable for manual Ruff runs,
or run them from `backend/api`. Pytest already runs from `backend/api`, so its cache
lands there too. `make clean-cache` also removes old cache copies from the repository
root; `make clean-build` removes `.next` and Playwright artifacts.

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
| `PRODUCTS_CSV_PATH`              | Development-only product export; defaults to `<repo>/data/parsina.csv`. When `products.json` sits beside it, the saved Parsina response is used instead, with unit titles from `units.json`.                                                                                                                                                      |

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

`/users` is available to the owner and admins. The owner sees every account and may create or delete `admin` and `viewer` accounts. An admin sees viewer accounts plus their own account and may create/delete viewers; the owner and other admins stay hidden. At least one management account always remains; since the owner cannot be deleted, the owner can remove every admin. Viewers get `403 forbidden` on every write. `/settings` is available to the owner and admins; the sidebar hides the سیستم group from viewers. See [AGENTS.md](AGENTS.md) and [ADR 010](docs/adr/010-owner-role.md).

```bash
GET    /api/v1/users          # owner: all accounts; admin: viewers + self
POST   /api/v1/users          # { "username", "password", "role": "admin" | "viewer" }
DELETE /api/v1/users/{id}     # also revokes that account's sessions
```

## Product data sources

Products mirror an external catalog (`external_id` = Parsina `goodId`), and the GET endpoints always read the local mirror. Where the mirror comes from depends on `APP_ENV`:

- **production** — live Parsina API (`PARSINA_*` credentials). The backend scheduler syncs at the interval configured in Settings (default `PARSINA_SYNC_INTERVAL_MINUTES`, 1440); the products page has a «به‌روزرسانی از پارسینا» button for a manual run.
- **development** — the saved Parsina export in `data/`: `products.json` (same field names as `GET /Commodity`, preferred when present) with count-unit titles from `units.json` (same `Id`/`Title` map as `GET /BaseInfo/UnitCount`). `make db-seed-parsina` upserts it into the dev product mirror; existing product ids, categories, and competitor links are kept and rows missing from the export are deactivated, never deleted. The same button re-imports the file. No Parsina credentials are needed; the scheduler ticks on the same interval, like production. If only the older `data/parsina.csv` is available, its `countUnit` ids are resolved to titles from `units.json` or the Parsina unit table in `parsina_csv.py`. `make db-seed-demo` additionally gives every active product demo competitor prices (Digikala/Technolife for appliances, Sofa for furniture, DigiFresh for carpets) with two daily observations, the missing suggested-price weights, and demo floor/ceiling percentages, so all products-table columns are populated in dev. Demo bounds rotate through four clamp scenarios — below the floor, above the ceiling, inside the bounds, and no bounds — so the suggested-price clamp is visible in the table; only bounds the seed itself wrote are refreshed, while an admin's saved clamp is kept. The rotation is keyed on the synced product identity (`external_id`, or SKU for manual rows), so dev and staging show the same demo prices and bounds even though the two databases assign different ids. Demo links use a `demo-` URL path; re-running refreshes only those rows and never touches real/manual links.

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

The legacy Neon-era production Make targets have been removed. Production uses the standalone
migration runner and explicit owner bootstrap as part of the ordered steps in the
[Production Docker stack](#production-docker-stack) and [AGENTS.md](AGENTS.md) section 3.

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

## API contract

Base path `/api/v1`. Interactive docs: Swagger UI at `/docs` (start the API with `make dev-api` or `make dev-all`, then open <http://localhost:8000/docs>) and ReDoc at `/redoc`. Log in through `POST /api/v1/auth/login`; the browser sends the resulting HttpOnly cookie automatically. Committed OpenAPI snapshot: [backend/api/openapi.json](backend/api/openapi.json) — regenerate after any route/schema change:

```bash
uv run --project backend/api python backend/api/scripts/export_openapi.py
```

The frontend client (`apps/web/lib/api.ts`) mirrors these shapes; see [AGENTS.md](AGENTS.md) section 11.

## Testing

- Frontend unit tests: `packages/ui/src/lib/*.test.ts` (vitest) — Persian digits, `٬` grouping, `٫` dates
- Frontend e2e: `apps/web/e2e/` (playwright) — unauthenticated redirects, Persian login form, RTL shell, mobile layout; runs against the production build without a backend — `pnpm --filter web test:e2e`
- Backend tests: `backend/api/tests/` (pytest) — auth flow, roles and user management, product CRUD, validation envelope
- CI runs lint, format check, typecheck, both test suites, the production build, and the Playwright e2e suite. Staging deploys through the Vercel/FastAPI Cloud Git integration.
- A `v*` tag triggers the release workflow, which verifies that commit, builds and pushes the API and web images, and only then publishes the GitHub Release with the verified digests in its body ([ADR 019](docs/adr/019-release-publication-after-image-verification.md)). Deployment is a separate, explicit operator step: `make prod-deploy` runs a single-slot, digest-pinned, health-gated script on the server (or over SSH with `SSH_HOST=...`) and deploys the newest published Release. It has not been executed yet; see [AGENTS.md](AGENTS.md) section 3, [ADR 018](docs/adr/018-simple-production-deploy.md) and [ADR 021](docs/adr/021-github-release-deploy-discovery.md). The earlier runner/Blue-Green design in ADR 016/017 is superseded.

## Build

```bash
make build
```

## Production Docker stack

Production uses a separate file, [compose.production.yml](compose.production.yml); it does not read
or extend [compose.local.yml](compose.local.yml). The stack is built for a Docker Engine host such as
`market-linux` but this repository does not deploy it and the stack is not live yet.

```bash
make prod-config    # validate compose structure; no secret files needed
make prod-build     # build pinned API + web production images from this checkout
make prod-pull      # pull the released API + web images by digest
make prod-up        # start db -> provision -> migrate -> api -> web -> caddy
make prod-provision # run idempotent role provisioning once (needs secrets)
make prod-migrate   # run the locked migration runner once (needs secrets)
make prod-ps        # service status and health
make prod-logs      # follow logs [SSH_HOST=...]
make prod-down      # stop services; volumes and data are kept

# One-command deploy of the newest published GitHub Release:
make prod-deploy                             # run locally on the host
make prod-deploy SSH_HOST=charsooq            # from a laptop, over SSH
# A specific version is optional: make prod-deploy VERSION=v1.2.3
# Rollback is the same command with the previous version tag.
```

`CHARSOOQ_GITHUB_REPO` in the host env file names the repository whose Releases are
discovered; a private repository additionally needs `GITHUB_TOKEN` exported in the
operator shell. The deploy script checks migrations with a read-only `--check` call
and only runs the one-shot migration service when a revision is pending.

`make prod-up` runs the one-shot `provision` and `migrate` services in order; the API is not
created until both succeed. `make prod-provision` and `make prod-migrate` run those same steps
manually as one-offs, and `make prod-bootstrap-owner` runs the explicit owner CLI. All of them need
real Production secrets; owner bootstrap remains a separate explicit step.

### Images and releases

Production runs **published images**, not a local build. `CHAHARSOQ_API_IMAGE` and
`CHARSOOQ_WEB_IMAGE` are required and have no default, so an unset reference stops the stack
instead of deploying whatever happens to be in the local image cache:

```bash
export CHAHARSOQ_API_IMAGE='ghcr.io/<owner>/chaharsooq-api@sha256:<digest>'
export CHARSOOQ_WEB_IMAGE='ghcr.io/<owner>/charsooq-web@sha256:<digest>'
```

Images are published by [`.github/workflows/release.yml`](.github/workflows/release.yml) when a
`v*` tag is pushed: that commit is verified, both images are built from it, tagged with the version
and the commit SHA, stamped with OCI metadata, and shipped with provenance and an SBOM. Only after
the images are verified is the GitHub Release published, with the digests in its body. The digest —
not the tag — is the deployment reference. See [AGENTS.md](AGENTS.md) section 3 and
[ADR 015](docs/adr/015-container-image-release-and-publishing.md) and
[ADR 019](docs/adr/019-release-publication-after-image-verification.md).

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
See [AGENTS.md](AGENTS.md) section 3 for the secret rules; the host commands are in the `Makefile`
targets.

Only the reverse proxy publishes a host port, and only on one approved internal IP: `caddy` binds
`80`/`443` (`${CHARSOOQ_PROXY_BIND_IP}`), while `db`, `provision`, `migrate`, `api`, and `web` listen
only on internal Compose networks (`web:3000`, `api:8000`, `db:5432`). Caddy reaches `web` through a
dedicated `proxy` network and has no route to the API or PostgreSQL. TLS termination, forwarded
headers, and HSTS are implemented in [`deploy/caddy`](deploy/caddy) and covered in [AGENTS.md](AGENTS.md)
section 3; no certificate is installed and the proxy is not deployed yet. Container logs are bounded
(`json-file`, 10 MB × 5 per service) so an unrotated stream cannot fill the host disk. The owner-only **Settings → پشتیبان‌گیری** page enables automatic backups (off by default, then every
7 days), queues a manual dump, uploads and downloads `pg_dump --format=custom` archives, and
restores shop data from a verified version. A background worker inside the API container runs the
pinned PostgreSQL 19 client with the application role (never the admin or migration credential) and
stores archives in the `chaharsooq-production_backups` volume; the restore is data-only and atomic,
runs behind a mandatory verified pre-restore dump, and leaves accounts, sessions, and backup history
untouched (see [ADR 023](docs/adr/023-in-app-backup-and-data-restore.md)). Archives are
**unencrypted and same-host only**: encryption/key custody, off-host transfer, PITR, and a rehearsed
restore drill remain unapproved and unimplemented (see
[ADR 014](docs/adr/014-production-backup-and-recovery.md)). PostgreSQL data
lives in the `chaharsooq-production_pgdata` volume at `/var/lib/postgresql` (the PostgreSQL 19
image's parent path; the cluster lives in a versioned subdirectory), and `make prod-down` never
removes either volume.

Operational rules: [AGENTS.md](AGENTS.md) section 3; decisions: [docs/adr/](docs/adr/).

## Deployment

Charsooq has three independent environments — Development, Staging, and Production. Each has its own secrets, database credentials (`DATABASE_URL`, plus `MIGRATION_DATABASE_URL` where role separation is used), and configuration; no Production data is copied automatically to Staging or Development. A push to `main` is not a Production release. See [AGENTS.md](AGENTS.md) section 3 for the rules.

- Development: local Next.js + FastAPI + PostgreSQL; `make local-up` / `make local-down` (short aliases of `make docker-up` / `make docker-down`) start/stop `web` + `api` + `postgres` from [compose.local.yml](compose.local.yml). It runs the locked migration runner first with `docker compose run --rm migrate`, so the one-shot container is removed when it finishes; a plain `docker compose up` is also safe because the API migrates in its Development lifespan. The development stack sets `APP_ENV=production` to exercise production behavior locally and `DEPLOYMENT_ENV=development` so it is never mistaken for Production. Both apps run in dev mode (`uvicorn --reload` and `next dev`) with the source bind-mounted, so code edits appear live without rebuilding the images; build once with `make docker-build` (Compose also builds a missing image on first up). `compose.local.yml` is the development stack, not a Production file. It declares only two volumes — `pgdata` (externally named `chaharsooq_pgdata19` for the PostgreSQL 19 cluster; the old `chaharsooq_pgdata` volume is kept untouched) and `backups` for archives — and mounts source directories individually so Docker creates no anonymous volumes (ADR 025).
- Staging: Vercel frontend (`vercel.json` pins pnpm install/build for the monorepo) + FastAPI Cloud backend (`make deploy-api`) + Neon database. Set `API_URL_INTERNAL` + `NEXT_PUBLIC_API_URL` to the Staging API origin in Vercel — the build fails fast if they still point at localhost. Browser calls same-origin `/api/*`; Next rewrites to the API origin, so the session cookie stays first-party. The API auto-migrates on boot in Staging.
- Production: Docker Engine + Docker Compose on Ubuntu `market-linux` (`172.30.2.2`): Next.js, FastAPI, and PostgreSQL 19.0, with separate administrative, migration, and application database roles. [compose.production.yml](compose.production.yml) encodes the service order (`db` → `provision` → `migrate` → `api` → `web` → `caddy`), file-backed secrets, internal networks, and health checks. The Caddy reverse proxy, TLS modes, and trusted-proxy design are implemented in [deploy/caddy](deploy/caddy) and [ADR 012](docs/adr/012-internal-reverse-proxy-and-tls.md) but not enabled against a real certificate. Backup execution (manual/scheduled dumps and transactional restores in the API container; see ADR 023), image registry/promotion, the IT-owned DNS/CA/IP decisions, and the actual server deployment remain open. Production is not live yet; see [AGENTS.md](AGENTS.md) section 3.
