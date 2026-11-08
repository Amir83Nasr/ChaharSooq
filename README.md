# چهارسوق (Charsooq)

Persian, RTL-first admin web application. Monorepo: Next.js frontend + FastAPI backend + PostgreSQL.

## Tech stack

- Frontend: Next.js 16, React 19, TypeScript (strict), Tailwind CSS 4, shadcn/ui, pnpm
- Backend: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, uv
- Database: PostgreSQL (compose pins postgres:18)

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

Each app owns its env file: [backend/api/.env.example](backend/api/.env.example) (copy to `backend/api/.env.local`) and [apps/web/.env.example](apps/web/.env.example) (copy to `apps/web/.env.local`). Never commit real secrets. The backend reads its env file by absolute path, so the API, Alembic, and the seed scripts always target the same configuration. A shared root `.env.local` (or `.env`) is also loaded by both apps as a fallback, which is convenient for LAN/mobile dev (e.g. whitelisting device IPs in `ALLOWED_DEV_ORIGINS` / `CORS_ORIGINS`); per-app values take precedence.

| Variable              | Purpose                                                                                                                                                                                                                                                   |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `APP_ENV`             | `development` / `test` / `production` (Secure cookies only in production)                                                                                                                                                                                 |
| `DATABASE_URL`        | SQLAlchemy URL, e.g. `postgresql+psycopg://charsooq:charsooq@localhost:5433/charsooq`                                                                                                                                                                     |
| `SESSION_SECRET`      | Session signing secret; change the dev default in production                                                                                                                                                                                              |
| `SESSION_SAMESITE`    | `lax` (same-site dev) / `none` (Vercel frontend + separate API host)                                                                                                                                                                                      |
| `API_URL_INTERNAL`    | Server-side API origin for Next `/api/*` rewrites; falls back to `NEXT_PUBLIC_API_URL`                                                                                                                                                                    |
| `NEXT_PUBLIC_API_URL` | API origin fallback for rewrites (browser always calls same-origin `/api/*`)                                                                                                                                                                              |
| `CORS_ORIGINS`        | Backend CORS allowlist, comma-separated                                                                                                                                                                                                                   |
| `ALLOWED_DEV_ORIGINS` | Extra Next.js dev origins, comma-separated                                                                                                                                                                                                                |
| `OWNER_USERNAME`      | Highest-privilege `owner` login. Defaults to `admin`. The API creates this account on boot and keeps it in sync with the env.                                                                                                                             |
| `OWNER_PASSWORD`      | Owner password. Required in production (minimum 8 characters). Changing it re-hashes the account and revokes its sessions on the next boot.                                                                                                               |
| `PARSINA_*`           | Parsina accounting API (URL, credentials, org, year, optional warehouse/sale-type). Empty = integration off. `PARSINA_SYNC_INTERVAL_MINUTES` (default 1440) seeds the initial auto-sync interval and `PARSINA_SYNC_ENABLED` toggles the backend scheduler |
| `PRODUCTS_CSV_PATH`   | Development-only product CSV; defaults to `<repo>/data/parsina.csv`                                                                                                                                                                                       |

## Roles and users

Accounts have one of three roles:

| Role     | Can do                                                                                             |
| -------- | -------------------------------------------------------------------------------------------------- |
| `owner`  | Everything, including creating/removing admins. Comes only from `OWNER_USERNAME`/`OWNER_PASSWORD`. |
| `admin`  | Shop data (products, categories, settings, sync) and viewer management. Never sees other admins.   |
| `viewer` | Read-only: catalog, dashboard, integration pages, and the settings values those views use.         |

`/users` is available to the owner and admins. The owner sees every account and may create `admin` or `viewer` accounts. An admin sees only viewer accounts and may create/delete viewers; the owner and other admins stay hidden. Viewers get `403 forbidden` on every write. `/settings` is available to the owner and admins; the sidebar hides the سیستم group from viewers. See [docs/architecture/authentication.md](docs/architecture/authentication.md) and [ADR 010](docs/adr/010-owner-role.md).

```bash
GET    /api/v1/users          # owner: all accounts; admin: viewers only
POST   /api/v1/users          # { "username", "password", "role": "admin" | "viewer" }
DELETE /api/v1/users/{id}     # also revokes that account's sessions
```

## Product data sources

Products mirror an external catalog (`external_id` = Parsina `goodId`), and the GET endpoints always read the local mirror. Where the mirror comes from depends on `APP_ENV`:

- **production** — live Parsina API (`PARSINA_*` credentials). The backend scheduler syncs at the interval configured in Settings (default `PARSINA_SYNC_INTERVAL_MINUTES`, 1440); the products page has a «به‌روزرسانی از پارسینا» button for a manual run.
- **development** — `data/parsina.csv` (an export of the live catalog, same field names). `make db-seed-parsina` upserts it into the dev product mirror; existing product ids, categories, and competitor links are kept and rows missing from the CSV are deactivated, never deleted. The same button re-imports the file. No Parsina credentials are needed; the scheduler ticks on the same interval from the CSV, like production. The export only carries `countUnit` ids, so the CSV source supplies mock unit titles to keep the dev catalog identical to production. `make db-seed-demo` additionally gives every active product demo competitor prices (Digikala/Technolife for appliances, Sofa for furniture, DigiFresh for carpets) with two daily observations, the missing suggested-price weights, and demo floor/ceiling percentages, so all products-table columns are populated in dev. Demo bounds rotate through four clamp scenarios — below the floor, above the ceiling, inside the bounds, and no bounds — so the suggested-price clamp is visible in the table; only bounds the seed itself wrote are refreshed, while an admin's saved clamp is kept. Demo links use a `demo-` URL path; re-running refreshes only those rows and never touches real/manual links.

Both paths share one validation/apply routine and one DB lock, so runs never overlap. Manual runs return `202` and the UI polls `GET /integrations/parsina/status` until the run finishes, then re-fetches the table in place. A failed or partial fetch never overwrites the last successful data; rows missing from a complete listing are deactivated, never deleted.

## Competitor prices

Competitor links and observations are stored separately from the Parsina catalog. In product details, admins can add Digikala, Technolife, or another public product URL; run a check; save a manual price/stock correction; disable the link; or delete it. Each product dialog also has a «به‌روزرسانی همه قیمت‌ها» button that re-checks all of its active links at once, and the products header has a «به‌روزرسانی قیمت رقبا» button that refreshes every active link in the background (poll `GET /integrations/competitors/status`, `409` while a run holds the lock). The same bulk refresh also runs automatically on a schedule set in Settings («فاصله به‌روزرسانی خودکار قیمت رقبا», default 24 hours). Automatic extraction is limited to Digikala and Technolife public product pages, uses JSON-LD product offers only, checks each host's `robots.txt`, validates redirects and public DNS, and stops for six hours after a `403` or `429`. Unknown stores remain manual-only. Prices expire after 24 hours by default and stale values are excluded from the table and competitor-price filters. Configure `COMPETITOR_REQUEST_INTERVAL_SECONDS` (default 5) and `COMPETITOR_PRICE_TTL_HOURS` (default 24) in `backend/api/.env.local`.

## Database setup

```bash
make db-migrate        # dev: start postgres + `alembic upgrade head`
make db-seed            # ensure the owner account from OWNER_USERNAME/OWNER_PASSWORD
make db-seed-parsina    # upsert dev product catalog from data/parsina.csv
make db-seed-demo       # demo competitor prices + daily changes for the products table
make db-sync-dev-to-prod # upsert dev data into prod; never deletes products or links
make db-sync-dev-to-staging # upsert dev data into staging Neon + demo prices (reads backend/api/.env.staging)
make db-seed-demo-staging # only refresh staging demo competitor prices (reads backend/api/.env.staging)

make db-migrate-prod                          # prod Neon: migrations (reads .env.production)
make db-seed-prod                             # prod Neon: ensure owner (OWNER_PASSWORD required)
```

## Migrations

Schema changes require an Alembic migration under `backend/api/migrations/`. Autogenerate from models, review, then apply (`make db-migrate`).

- The API runs `upgrade head` on every boot (except tests), so deploys never need a manual migration — locally, in Docker, or on FastAPI Cloud.
- CI proves it: fresh `upgrade head`, idempotent re-upgrade, single-head assertion, `alembic check` drift detection, and a downgrade/upgrade round-trip.
- `make db-validate` runs the offline part locally (no database needed); `make check` includes it.

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
- CI runs lint, format check, typecheck, both test suites, the production build, and the Playwright e2e suite; deploy happens only after CI succeeds.

## Build

```bash
make build
```

## Deployment

- Frontend: Vercel (`vercel.json` pins pnpm install/build for the monorepo). Set `API_URL_INTERNAL` + `NEXT_PUBLIC_API_URL` to the API origin in Vercel Production env — the build fails fast if they still point at localhost. Browser calls same-origin `/api/*`; Next rewrites to the API origin, so the session cookie stays first-party.
- Backend: FastAPI Cloud (`make deploy-api`). Set `APP_ENV=production`, real `DATABASE_URL`, strong `SESSION_SECRET`. Migrations run automatically on boot — no manual step.
- Docker: `make docker-up` runs `web` + `api` + `postgres` from [compose.yml](compose.yml); a one-shot `migrate` service applies Alembic before the API starts.
- See [docs/architecture/deployment.md](docs/architecture/deployment.md).
