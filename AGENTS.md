# AGENTS.md

Constraints for coding agents on **چهارسوق (Charsooq)**, a Persian, RTL-first admin panel. Setup: [README.md](README.md). Contribution: [CONTRIBUTING.md](CONTRIBUTING.md). Architecture: [docs/](docs/README.md).

## 1. Repository map

| Path | Contents |
| --- | --- |
| `apps/web` | Next.js app: routes, app-level components, API client, e2e tests |
| `packages/ui` | Shared UI kit: shadcn primitives, Persian formatting, global styles |
| `packages/eslint-config`, `packages/typescript-config` | Shared ESLint and TypeScript configs |
| `backend/api` | FastAPI service: `app/`, `migrations/`, `tests/`, `scripts/` |
| `backend/api/openapi.json` | Committed OpenAPI snapshot. Generated; never edit by hand |
| `docs/` | Architecture notes, ADRs, API notes |
| `.github/workflows/` | CI and deploy |
| `Dockerfile.*`, `compose.yml` | Container images and the local stack |
| `data/` | Local-only data files (gitignored) |

Do not add a workspace or top-level folder without a documented reason (an ADR).

## 2. Toolchain

- Node 22 (`.node-version`) and pnpm 11 only. No npm/yarn.
- Python 3.12 (`.python-version`) and uv only. No pip/Poetry.
- `pnpm-lock.yaml` and `uv.lock` are authoritative. Install with `pnpm install --frozen-lockfile` and `uv sync --locked`.
- Never write `latest` into a manifest. Before adding a dependency, confirm the need is real and an existing dependency/stdlib cannot cover it.

## 3. Architecture boundaries

### Backend

Dependency flow: `api/routes → services → repositories → database`.

- Route handlers parse input, call one service, and return the result. No business logic and no SQL.
- Services hold business logic. Repositories own all SQLAlchemy 2.x queries.
- Pydantic schemas in `app/schemas/` are the only API boundary types. ORM models do not leave the repository layer.
- Schema changes go through Alembic migrations in `migrations/`. `create_all` is allowed only in tests and dev seed scripts.
- External APIs (for example Parsina) live in `app/integrations/`.

### Frontend

- `packages/ui` holds generic, reusable UI. No business logic, no API calls, no app routes.
- `apps/web/components/` holds app-level composites (sidebar, header, theme, settings).
- `apps/web/app/**/_components/` holds components private to one route segment.
- `apps/web/lib/` holds the API client, auth helpers, and app domain helpers.
- Keep data fetching out of presentational components.

## 4. UI system

- shadcn/ui is the UI system. Use official components and Blocks before writing custom ones. Style with Tailwind CSS 4.
- Do not add another component library without an ADR.
- The main sidebar uses the shadcn Sidebar / Block approach.
- Code in `packages/ui` must not import from `apps/web`.

## 5. RTL and fonts

- The root document uses `lang="fa"` and `dir="rtl"`.
- Design for RTL, not only for text alignment. Use logical properties (`margin-inline`, `padding-inline`, `inset-inline-*`, `start`/`end`). Do not add LTR hacks unless a technical value requires one.
- Check drawers, dialogs, dropdowns, tables, navigation, icons, and alignment in RTL.
- Main UI font: **IRANYekanX**, defined only in `apps/web/app/fonts.ts`. Do not substitute another Persian font while it is available.
- Toman glyph: render prices only through the `<Price />` component in `packages/ui`. Do not copy glyph markup into features. The glyph font file is not in the repo yet; until it is, `.toman-glyph` falls back (see [ADR 004](docs/adr/004-persian-formatting.md)).

## 6. Numbers, dates, currency

Machine and display representations are separate.

- **Machine values** (backend, API, calculations, database): plain numbers such as `1000000`, integer toman, UTC datetimes. Never store Persian digits or Jalali strings.
- **Display values** (UI only), all implemented in `packages/ui/src/lib/`:
  - Digits: Persian `۰–۹`.
  - Thousands separator: `٬` (U+066C). Example: `۱٬۰۰۰٬۰۰۰`. Never `,`.
  - Dates: Jalali calendar with `٫` (U+066B) as the separator. Example: `۱۴۰۵٫۰۵٫۰۵`. Never `/`, `-`, or `.`.
  - Currency: تومان. Use `<Price value={…} />`, which applies the digits, grouping, and glyph. Pass the numeric source value.

Do not write digit conversion, date formatting, or raw `تومان` strings in feature files.

## 7. Authentication and security

This is an admin panel with password login.

- Hash passwords with Argon2id (`argon2-cffi`). Never store or log plaintext passwords.
- Use server-managed sessions with the session ID in an HttpOnly cookie. Set `Secure` in production and an explicit `SameSite` policy.
- Rate-limit login attempts.
- Do not store auth tokens in `localStorage` or `sessionStorage`.
- Never log passwords, session IDs, API keys, secrets, or Authorization headers.
- Never commit secrets. Only the per-app `.env.example` files (`backend/api/`, `apps/web/`) are tracked. Docker builds must not receive `.env*` files (see `.dockerignore`).
- Dev-only default credentials may exist in dev targets. Production seeding must receive `ADMIN_PASSWORD` explicitly.

## 8. Coding standards

### TypeScript

- `strict` mode, inherited from `@workspace/typescript-config`.
- No `any` unless it is unavoidable, and then comment the reason.
- Explicit, narrow types. Keep components focused. Keep business logic out of presentational components.

### Python

- Type hints on all functions. Pyright runs in `strict` mode.
- Small, focused functions. Ruff handles lint and format (line length 100).
- Do not catch broad `Exception` to hide errors.

### All code

- Match the surrounding file's naming, comment density, and idiom.
- Do not refactor unrelated code in a focused change.

## 9. Testing

- Changes in behavior need tests. Priorities: auth, money and Persian formatting, Jalali dates, API validation, database behavior, critical UI flows, and error states.
- Frontend unit tests: Vitest in `packages/ui/src/**/*.test.ts`.
- Frontend e2e: Playwright in `apps/web/e2e/`.
- Backend: pytest in `backend/api/tests/`, with shared fixtures in `conftest.py`.
- Do not claim a feature works if its tests are missing or failing. When a check was not run, say so.

## 10. Commands

Run from the repository root. `make help` lists every target.

- **Install:** `make install` (pnpm, uv, git hooks).
- **Lint:** `pnpm lint` and `uv run --project backend/api ruff check .`.
- **Format check:** `pnpm format:check` and `uv run --project backend/api ruff format --check .`.
- **Typecheck:** `pnpm typecheck` and `uv run --project backend/api pyright`.
- **Test:** `pnpm test` and `uv run --project backend/api pytest -q`.
- **Build:** `pnpm --filter web build`.
- **Everything:** `make check` (lint, typecheck, test).

Use the `make` targets when they exist.

## 11. Git, hooks, CI

- Hooks are managed by Lefthook (`lefthook.yml`). `pre-commit` runs fast checks on staged files. `pre-push` runs the broader checks. Do not weaken a hook to get a change through.
- CI (`.github/workflows/ci.yml`) must stay green: frozen pnpm install, `uv sync --locked`, frontend lint, typecheck and tests, backend ruff, pyright and pytest against PostgreSQL, and the production build.
- Keep workflow permissions minimal (`contents: read` by default). Never print secrets in logs.
- Commit messages follow the Conventional Commits style used in history, for example `feat(web): …` or `fix(api): …`.

## 12. Documentation

Documentation is part of the change.

- If behavior, setup, commands, env vars, or user-visible rules change, update `README.md`, `CONTRIBUTING.md`, or `docs/`.
- If a route or schema changes, regenerate the snapshot with `uv run --project backend/api python backend/api/scripts/export_openapi.py` and update the types in `apps/web/lib/api.ts`.
- A new env var goes into the owning app's `.env.example` (`backend/api/` or `apps/web/`) and the README table.
- A significant architecture decision needs a new ADR in `docs/adr/`. Use the next number and never renumber.

## 13. Definition of done

A task is done when all of these hold:

- [ ] The implementation is complete, and its tests are added or updated and pass.
- [ ] Lint, typecheck, format check, and the affected tests pass (see §10).
- [ ] UI changes are verified in RTL: digits, separators, dates, and prices use the Persian rules; loading, empty, and error states exist; mobile, tablet, and desktop layouts are intentional; keyboard access works.
- [ ] Docs and the OpenAPI snapshot are updated where required.
- [ ] The diff has no secrets, generated noise, or unrelated changes.

Build the smallest solution that fits the existing architecture. Optimize for correctness, security, maintainability, and consistency, not for cleverness, brevity, or new libraries.

<!-- BEGIN:turborepo-agent-rules -->

# This is NOT the Turborepo you know

Turborepo configuration, task behavior, and CLI commands can vary between installed versions and may differ from your training data. Resolve the `turbo` package from this file's directory or relevant workspace; in monorepos, it may not be visible from the repository root. For example, run `node -p "require.resolve('turbo/package.json')"` from a workspace that depends on `turbo`.

Read `docs/README.md` inside that installed package first, then read the relevant pages from its `docs/` directory before changing Turborepo configuration or commands. Heed deprecation notices. These bundled docs match the installed package version and are available without network access.

This block is written and re-added by `turbo` before repository-scoped commands when an AI agent is detected. In the Turborepo source repository, its template is defined in `crates/turborepo-cli/src/cli/agent_guidance.rs`. Removing the managed block while updates are enabled means a later qualifying invocation will add it again. Set `"agentGuidance": false` in the root `turbo.json` or `turbo.jsonc` to opt out; do not remove an existing block. Keep the block committed with your work to avoid an uncommitted change on the next agent invocation.
<!-- END:turborepo-agent-rules -->
