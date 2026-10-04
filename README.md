# چهارسوق (Charsooq)

Persian, RTL-first admin web application. Monorepo: Next.js frontend + FastAPI backend + PostgreSQL.

## Tech stack

- Frontend: Next.js 16, React 19, TypeScript (strict), Tailwind CSS 4, shadcn/ui, pnpm
- Backend: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, uv
- Database: PostgreSQL 17

See [CHARSOOQ-PROJECT-SPEC.md](CHARSOOQ-PROJECT-SPEC.md) for full specification and [AGENTS.md](AGENTS.md) for agent rules.

## Requirements

- Node.js >= 20.9, pnpm 11
- Python >= 3.12, uv
- PostgreSQL 17 (or Docker)

## Installation

```bash
pnpm install
uv sync
cp .env.example .env.local
```

## Development commands

Run everything from the repository root with make:

```bash
make install    # install frontend + backend deps
make db-up      # start dev postgres (compose)
make migrate    # apply Alembic migrations
make seed       # create dev admin (ADMIN_USER / ADMIN_PASSWORD)
make dev-all    # postgres + migrate, then backend :8000 + frontend :3000
```

Individual servers:

```bash
make api        # backend API with reload (:8000, expects postgres up)
make dev        # frontend only (turbo)
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
| `SESSION_SECRET` | Reserved for session signing; change the dev default in production |
| `NEXT_PUBLIC_API_URL` | Frontend → API base URL |

## Database setup

```bash
createdb charsooq
uv run --project backend/api alembic -c backend/api/alembic.ini upgrade head
```

## Migrations

Schema changes require an Alembic migration under `backend/api/migrations/`. Autogenerate from models, review, then apply.

## Testing

- Frontend unit tests: `packages/ui/src/lib/*.test.ts` (vitest) — Persian digits, `٬` grouping, `٫` dates
- Backend tests: `backend/api/tests/` (pytest) — auth flow, product CRUD, validation envelope
- CI runs both plus a production build; PostgreSQL service for backend integration.

## Build

```bash
pnpm --filter web build
```

## Deployment

- Frontend: any Node 22 host (`next start`) behind TLS.
- Backend: `uvicorn app.main:app` from `backend/api` with `APP_ENV=production`, real `DATABASE_URL`, and a strong `SESSION_SECRET`.
- See [docs/architecture/deployment.md](docs/architecture/deployment.md).
