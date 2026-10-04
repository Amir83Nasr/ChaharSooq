# Testing — چهارسوق

- Frontend (vitest, `@workspace/ui`): `pnpm --filter @workspace/ui test` — digits, `٬` grouping, `٫` Jalali dates, Toman formatting.
- Backend (pytest, `backend/api`): `uv run --project backend/api pytest -q` — health, login 401/200, me guard, login→me→logout cycle, product auth guard, CRUD roundtrip (numeric price), validation envelope.
- DB: tests run SQLite in-memory by default; CI adds PostgreSQL 17 service with `DATABASE_URL` for integration parity.
- E2E (Playwright, `apps/web`): `pnpm --filter web test:e2e` — root redirect + fa/rtl shell, Persian login form, dashboard Persian KPIs, mobile drawer nav. Full login→products mutation flow needs a running API + seeded admin; hooks (`lefthook.yml`) and CI (`.github/workflows/ci.yml`, `e2e.yml`) gate lint/typecheck/tests/build.
