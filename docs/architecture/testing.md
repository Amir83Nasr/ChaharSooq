# Testing — چهارسوق

- Frontend (vitest, `@workspace/ui`): `pnpm --filter @workspace/ui test` — digits, `٬` grouping, `٫` Jalali dates, Toman formatting, `<Price />` markup.
- Backend (pytest, `backend/api`): `cd backend/api && uv run --no-sync pytest -q` — health + security headers, login 401/200/429 rate-limit, me guard, login→me→logout cycle, product auth guard, CRUD roundtrip (numeric price), validation envelope.
- DB: tests run SQLite in-memory by default; CI adds a PostgreSQL 18 service with `DATABASE_URL` for integration parity.
- E2E (Playwright, `apps/web`): `pnpm --filter web test:e2e` — unauthenticated redirects (`/`, `/products`, `/dashboard`, `/settings` → `/login`), fa/rtl shell, Persian login form (submit disabled until filled), mobile layout. Runs against the production build with no backend. The full login→products mutation flow needs a running API + seeded admin. `lefthook.yml` (pre-push) and `.github/workflows/ci.yml` gate lint, format check, typecheck, tests, build, and e2e.
