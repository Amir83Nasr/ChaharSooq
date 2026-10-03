# Contributing — چهارسوق

## Setup

```bash
pnpm install
uv sync
cp .env.example .env.local
```

## Workflow

1. Branch from `main`, keep changes focused.
2. Follow [AGENTS.md](../AGENTS.md) and [CHARSOOQ-PROJECT-SPEC.md](../CHARSOOQ-PROJECT-SPEC.md).
3. Machine values stay numeric/Latin in backend, API, and DB. Persian digits, `٬`, `٫`, Jalali dates, and the Toman glyph live only in the UI layer (`packages/ui`).
4. Business logic goes in `backend/api/app/services/`, never in route handlers. UI primitives stay free of business logic.

## Checks (must pass before push)

```bash
pnpm lint && pnpm typecheck
pnpm --filter @workspace/ui test
pnpm --filter web build
uv run --project backend/api ruff check .
uv run --project backend/api ruff format --check .
uv run --project backend/api pyright
uv run --project backend/api pytest -q
```

Lefthook runs fast checks on commit and the full set on push.

## Docs

Update `docs/` and `README.md` alongside behavior changes. Significant architectural decisions need an ADR under `docs/adr/`.
