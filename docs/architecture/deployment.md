# Deployment — چهارسوق

## Frontend (`apps/web`)

```bash
pnpm install --frozen-lockfile
pnpm --filter web build
pnpm --filter web start  # or `next start` on the host
```

Set `NEXT_PUBLIC_API_URL` to the API origin. Serve behind TLS.

## Backend (`backend/api`)

```bash
uv sync --project backend/api
uv run --project backend/api alembic -c backend/api/alembic.ini upgrade head
APP_ENV=production DATABASE_URL=postgresql+psycopg://... SESSION_SECRET=<strong> \
  uv run --project backend/api uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Production requires: real `DATABASE_URL`, strong `SESSION_SECRET`, `APP_ENV=production` (enables `Secure` cookies), restricted `CORS_ORIGINS`.

## Docker (optional)

`compose.yml` provides `web` + `api` + `postgres` for reproducible local/prod-like runs. Native `pnpm dev` remains the default dev path.
