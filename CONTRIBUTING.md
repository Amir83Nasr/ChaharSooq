# Contributing — چهارسوق

## Setup

```bash
make install            # pnpm install, uv sync --locked, git hooks
cp backend/api/.env.example backend/api/.env.local
cp apps/web/.env.example apps/web/.env.local
```

## Workflow

1. Branch from `main`, keep changes focused.
2. Follow [AGENTS.md](AGENTS.md): it defines the architecture boundaries, formatting rules, and definition of done.
3. Machine values stay numeric/Latin in backend, API, and DB. Persian digits, `٬`, `٫`, Jalali dates, and the Toman glyph live only in the UI layer (`packages/ui`).
4. Business logic goes in `backend/api/app/services/`, never in route handlers. UI primitives stay free of business logic.

## Checks (must pass before push)

```bash
make check    # lint + typecheck + tests (frontend and backend)
make build    # production web build
```

`make help` lists the individual targets. The same checks run in CI (`.github/workflows/ci.yml`).

Lefthook runs fast checks on commit (formatting, lint, ruff on staged files) and the broader checks on push. Do not bypass them with `--no-verify` unless a maintainer asks you to.

## Docs

Update `docs/` and `README.md` alongside behavior changes. Significant architectural decisions need an ADR under `docs/adr/`.
