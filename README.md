# چهارسوق (Charsooq)

Persian, RTL-first admin web application. Monorepo: Next.js frontend + FastAPI backend + PostgreSQL.

## Tech stack

- Frontend: Next.js 16, React 19, TypeScript (strict), Tailwind CSS 4, shadcn/ui, pnpm
- Backend: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, uv
- Database: PostgreSQL (compose pins postgres:18)

See [docs/architecture/overview.md](docs/architecture/overview.md) for architecture and [AGENTS.md](AGENTS.md) for agent rules.

## Requirements

- Node.js >= 20.9, pnpm 11
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
make db-seed           # create dev admin (DEV_ADMIN_PASSWORD, default secret123)
make db-seed-parsina   # load data/parsina-products.csv into the dev catalog (replaces products)
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
uv run --project backend/api pytest -q             # backend tests
```

## Environment variables

Each app owns its env file: [backend/api/.env.example](backend/api/.env.example) (copy to `backend/api/.env.local`) and [apps/web/.env.example](apps/web/.env.example) (copy to `apps/web/.env.local`). Never commit real secrets. The backend reads its env file by absolute path, so the API, Alembic, and the seed scripts always target the same configuration. A shared root `.env.local` (or `.env`) is also loaded by both apps as a fallback, which is convenient for LAN/mobile dev (e.g. whitelisting device IPs in `ALLOWED_DEV_ORIGINS` / `CORS_ORIGINS`); per-app values take precedence.

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `development` / `test` / `production` (Secure cookies only in production) |
| `DATABASE_URL` | SQLAlchemy URL, e.g. `postgresql+psycopg://charsooq:charsooq@localhost:5433/charsooq` |
| `SESSION_SECRET` | Session signing secret; change the dev default in production |
| `SESSION_SAMESITE` | `lax` (same-site dev) / `none` (Vercel frontend + separate API host) |
| `API_URL_INTERNAL` | Server-side API origin for Next `/api/*` rewrites; falls back to `NEXT_PUBLIC_API_URL` |
| `NEXT_PUBLIC_API_URL` | API origin fallback for rewrites (browser always calls same-origin `/api/*`) |
| `CORS_ORIGINS` | Backend CORS allowlist, comma-separated |
| `ALLOWED_DEV_ORIGINS` | Extra Next.js dev origins, comma-separated |
| `ADMIN_USER` / `ADMIN_PASSWORD` | Admin seed credentials. `make db-seed` uses `ADMIN_PASSWORD` or `DEV_ADMIN_PASSWORD` (default `secret123`). `make db-seed-prod` **requires** `ADMIN_PASSWORD=…` on the command line |
| `PARSINA_*` | Parsina accounting API (URL, credentials, org, year, optional warehouse/sale-type). Empty = integration off. `PARSINA_SYNC_INTERVAL_MINUTES` (default 60) seeds the initial auto-sync interval and `PARSINA_SYNC_ENABLED` toggles the backend scheduler |
| `PRODUCTS_CSV_PATH` | Development-only product CSV; defaults to `<repo>/data/parsina-products.csv` |

## Product data sources

Products mirror an external catalog (`external_id` = Parsina `goodId`), and the GET endpoints always read the local mirror. Where the mirror comes from depends on `APP_ENV`:

- **production** — live Parsina API (`PARSINA_*` credentials). The backend scheduler syncs at the interval configured in Settings (default `PARSINA_SYNC_INTERVAL_MINUTES`, 60); the products page has a «به‌روزرسانی اطلاعات» button for a manual run.
- **development** — `data/parsina-products.csv` (an export of the live catalog, same field names). `make db-seed-parsina` loads it and replaces the dev product mirror; the same button re-imports the file. No Parsina credentials are needed and the scheduler stays off. The export only carries `countUnit` ids, so the CSV source supplies mock unit titles to keep the dev catalog identical to production.

Both paths share one validation/apply routine and one DB lock, so runs never overlap. Manual runs return `202` and the UI polls `GET /integrations/parsina/status` until the run finishes, then re-fetches the table in place. A failed or partial fetch never overwrites the last successful data; rows missing from a complete listing are deactivated, never deleted.

## Database setup

```bash
make db-migrate        # dev: start postgres + `alembic upgrade head`
make db-seed            # dev admin user
make db-seed-parsina    # dev product catalog from data/parsina-products.csv

make db-migrate-prod                          # prod Neon: migrations (reads .env.production)
make db-seed-prod ADMIN_PASSWORD=<password>   # prod Neon: admin user (password required)
```

## Migrations

Schema changes require an Alembic migration under `backend/api/migrations/`. Autogenerate from models, review, then apply (`make db-migrate`).

## API contract

Base path `/api/v1`. Committed OpenAPI snapshot: [backend/api/openapi.json](backend/api/openapi.json) — regenerate after any route/schema change:

```bash
uv run --project backend/api python backend/api/scripts/export_openapi.py
```

The frontend client (`apps/web/lib/api.ts`) mirrors these shapes; see [docs/api/README.md](docs/api/README.md).

## Testing

- Frontend unit tests: `packages/ui/src/lib/*.test.ts` (vitest) — Persian digits, `٬` grouping, `٫` dates
- Frontend e2e: `apps/web/e2e/` (playwright) — unauthenticated redirects, Persian login form, RTL shell, mobile layout; runs against the production build without a backend — `pnpm --filter web test:e2e`
- Backend tests: `backend/api/tests/` (pytest) — auth flow, product CRUD, validation envelope
- CI runs lint, format check, typecheck, both test suites, the production build, and the Playwright e2e suite; deploy happens only after CI succeeds.

## Build

```bash
make build
```

## Deployment

- Frontend: any Node 22 host (`next start`) behind TLS. Browser calls same-origin `/api/*`; Next rewrites to the API origin (`API_URL_INTERNAL`, else `NEXT_PUBLIC_API_URL`), so the session cookie stays first-party.
- Backend: `uv run --project backend/api uvicorn app.main:app --app-dir backend/api --host 0.0.0.0 --port 8000` with `APP_ENV=production`, real `DATABASE_URL`, and a strong `SESSION_SECRET`. Or `make deploy-api` (FastAPI Cloud).
- Docker: `make docker-up` runs `web` + `api` + `postgres` from [compose.yml](compose.yml); a one-shot `migrate` service applies Alembic before the API starts.
- See [docs/architecture/deployment.md](docs/architecture/deployment.md).
