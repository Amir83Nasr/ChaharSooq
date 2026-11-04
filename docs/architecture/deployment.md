# Deployment — چهارسوق

No manual migrations, no manual redeploys. The pipeline enforces it:

1. `pre-push` hook runs lint, typecheck, tests, and an offline migration
   validation — a broken push never leaves the machine.
2. CI (`ci.yml`) runs frontend checks, backend checks on PostgreSQL, the
   **migrations** job (fresh `upgrade head`, idempotent re-upgrade, single
   head, `alembic check` drift detection, downgrade/upgrade round-trip), the
   production build, and Playwright e2e.
3. Push to `main` → Vercel rebuilds the frontend, FastAPI Cloud restarts the
   API, and the API migrates itself on boot.

## Frontend — Vercel (`apps/web`)

Root `vercel.json` pins the monorepo commands (`pnpm install
--frozen-lockfile`, `pnpm --filter web build`, `apps/web/.next`) so Vercel
never falls back to npm or a wrong workspace root.

Required **Production** environment variables (Vercel dashboard → Project →
Settings → Environment Variables):

| Variable              | Value                                                                 |
| --------------------- | --------------------------------------------------------------------- |
| `API_URL_INTERNAL`    | FastAPI origin, e.g. `https://….fastapicloud.dev` (no trailing slash) |
| `NEXT_PUBLIC_API_URL` | Same FastAPI origin (fallback for the rewrite target)                 |

The `build` script runs `scripts/check-vercel-env.mjs` first: a production
build with a loopback API origin fails fast with a clear message instead of
shipping a frontend that proxies to itself. After changing env vars, use
Vercel's **Redeploy** (no cache clear needed — a changed env var already
invalidates the build).

Browser calls always hit same-origin `/api/*`; Next rewrites to the API
origin, so the session cookie stays first-party.

## Backend — FastAPI Cloud (`backend/api`)

Deploy with `make deploy-api` (runs `fastapi deploy` from `backend/api`).
Set in the FastAPI Cloud dashboard: `APP_ENV=production`, real
`DATABASE_URL` (Neon), strong `SESSION_SECRET` (≥ 32 chars), restricted
`CORS_ORIGINS`, `SESSION_SAMESITE=none`.

**Migrations are automatic.** `app/core/migrations.py::upgrade_to_head`
runs in the FastAPI lifespan on every boot (except `APP_ENV=test`), with a
short retry for multi-replica deploy races. `make db-migrate-prod` remains
only as a manual fallback.

## Docker (optional local/prod-like run)

`compose.yml` provides `migrate` + `api` + `web` + `postgres`. The one-shot
`migrate` service runs `alembic upgrade head` and `api` starts only after it
succeeds; both run from the same non-root `Dockerfile.api` image. Native
`pnpm dev` remains the default dev path.

```bash
make docker-up   # build + start web (:3000) + api (:8000) + postgres (:5433)
make docker-logs # follow logs
make docker-down # stop
```

## Local runs

```bash
make doctor      # toolchain, env files, postgres health, single migration head
make dev-all     # postgres + migrate, then backend :8000 + frontend :3000
make db-validate # offline migration check (no DB): single head + SQL renders
make check       # lint + typecheck + test + db-validate
```
