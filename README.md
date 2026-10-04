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
pnpm install
uv sync
cp .env.example .env.local
```

## Development commands

Run everything from the repository root with make (`make help` lists all targets):

```bash
make install           # install frontend + backend deps
make db-up             # start dev postgres (compose, host :5433)
make db-migrate        # apply Alembic migrations to dev database
make db-seed           # create dev admin (ADMIN_USER / ADMIN_PASSWORD)
make db-seed-products  # seed home-appliance catalog (idempotent, prunes stale rows)
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
pnpm format       # frontend format
pnpm --filter @workspace/ui test   # frontend unit tests
pnpm --filter web build            # production build

uv run --project backend/api ruff check .          # backend lint
uv run --project backend/api ruff format --check . # backend format check
uv run --project backend/api pyright               # backend typecheck
uv run --project backend/api pytest -q             # backend tests
```

## Environment variables

See [.env.example](.env.example). Never commit real secrets.

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
| `ADMIN_USER` / `ADMIN_PASSWORD` | Seed credentials for `db-seed` / `db-seed-prod` |

## Database setup

```bash
make db-migrate        # dev: start postgres + `alembic upgrade head`
make db-seed            # dev admin user
make db-seed-products   # home-appliance catalog

make db-migrate-prod db-seed-prod   # prod Neon (reads .env.production)
```

## Migrations

Schema changes require an Alembic migration under `backend/api/migrations/`. Autogenerate from models, review, then apply (`make db-migrate`).

## API contract

Base path `/api/v1`. Committed OpenAPI snapshot: [backend/openapi.json](backend/openapi.json) — regenerate after any route/schema change:

```bash
uv run --project backend/api python backend/api/scripts/export_openapi.py
```

The frontend client (`apps/web/lib/api.ts`) mirrors these shapes; see [docs/api/README.md](docs/api/README.md).

## Testing

- Frontend unit tests: `packages/ui/src/lib/*.test.ts` (vitest) — Persian digits, `٬` grouping, `٫` dates
- Frontend e2e: `apps/web/e2e/` (playwright, backend-free shell/form checks) — `pnpm --filter web test:e2e`
- Backend tests: `backend/api/tests/` (pytest) — auth flow, product CRUD, validation envelope
- CI runs both plus a production build; PostgreSQL service for backend integration.

## Build

```bash
make build
```

## Deployment

- Frontend: any Node 22 host (`next start`) behind TLS. Browser calls same-origin `/api/*`; Next rewrites to the API origin (`API_URL_INTERNAL`, else `NEXT_PUBLIC_API_URL`), so the session cookie stays first-party.
- Backend: `uv run --project backend/api uvicorn app.main:app --app-dir backend/api --host 0.0.0.0 --port 8000` with `APP_ENV=production`, real `DATABASE_URL`, and a strong `SESSION_SECRET`. Or `make deploy-api` (FastAPI Cloud).
- Docker: `make docker-up` runs `web` + `api` + `postgres` from [compose.yml](compose.yml).
- See [docs/architecture/deployment.md](docs/architecture/deployment.md).
