# AGENTS.md

Constraints for coding agents on **چهارسوق (Charsooq)**, a Persian, RTL-first admin panel.
Setup: [README.md](README.md); contributions: [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

This file is the single source of agent rules. Other documents:

- [docs/adr/](docs/adr/) — decisions, append-only; never renumber or delete.
- [Parsina API contract](docs/parsina-api.pdf) — source of truth (not the `data/` fixtures).
  When you need to read the Parsina documentation, read
  [docs/parsina-api.md](docs/parsina-api.md) — a derived, searchable Markdown transcription;
  the PDF remains authoritative.

| Area                     | Decisions                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Foundation (001–004)     | [Monorepo](docs/adr/001-monorepo.md), [authentication](docs/adr/002-authentication.md), [database](docs/adr/003-database.md), [Persian formatting](docs/adr/004-persian-formatting.md)                                                                                                                                                                                 |
| Dev & UX (005–008)       | [Dev DB sync](docs/adr/005-dev-db-sync-simulation.md), [dev scheduler](docs/adr/006-dev-scheduler.md), [motion performance](docs/adr/007-sidebar-theme-motion-performance.md), [perf/security](docs/adr/008-perf-security-hardening.md)                                                                                                                                |
| Roles (009–010)          | [Roles](docs/adr/009-role-based-access.md) (superseded), [owner](docs/adr/010-owner-role.md)                                                                                                                                                                                                                                                                           |
| Infrastructure (011–014) | [Environments](docs/adr/011-three-environment-architecture.md), [proxy/TLS](docs/adr/012-internal-reverse-proxy-and-tls.md), [TLS lifecycle](docs/adr/013-tls-certificate-lifecycle.md), [backup](docs/adr/014-production-backup-and-recovery.md)                                                                                                                      |
| Release (015–019)        | [Images](docs/adr/015-container-image-release-and-publishing.md) (partly superseded), [runner deploy](docs/adr/016-ci-cd-deploy-job.md) (superseded), [blue-green](docs/adr/017-blue-green-deployment.md) (superseded), [simple deploy](docs/adr/018-simple-production-deploy.md), [release publication](docs/adr/019-release-publication-after-image-verification.md) |
| Deploy discovery (021)   | [GitHub release discovery](docs/adr/021-github-release-deploy-discovery.md)                                                                                                                                                                                                                                                                                            |
| Catalog (020)            | [Digital section keywords](docs/adr/020-digital-section-keywords.md)                                                                                                                                                                                                                                                                                                   |
| Backup metadata (022)    | [Owner-configured backup orchestration](docs/adr/022-owner-configured-backup-orchestration.md) (execution superseded by 023)                                                                                                                                                                                                                                           |
| Backup execution (023)   | [In-app backup execution and transactional data restore](docs/adr/023-in-app-backup-and-data-restore.md) (restore-request flow superseded by 026)                                                                                                                                                                                                                      |
| Local dev (024)          | [Local compose hot reload](docs/adr/024-local-compose-hot-reload.md) (web mounts superseded by 025)                                                                                                                                                                                                                                                                    |
| Local volumes (025)      | [No anonymous volumes in the local stack](docs/adr/025-local-compose-no-anonymous-volumes.md)                                                                                                                                                                                                                                                                          |
| Restore execution (026)  | [Direct owner restore](docs/adr/026-direct-owner-restore.md)                                                                                                                                                                                                                                                                                                           |
| Schedule defaults (027)  | [Backup schedule defaults in days](docs/adr/027-backup-schedule-defaults.md) (overrides schedule defaults in 023)                                                                                                                                                                                                                                                      |
| PostgreSQL 19 (028)      | [PostgreSQL 19 upgrade readiness](docs/adr/028-postgresql-19-upgrade-readiness.md) (supersedes version statements in 003/008/014/023)                                                                                                                                                                                                                                  |
| Backup page (029)        | [Standalone backup page in the system sidebar](docs/adr/029-standalone-backup-page.md) (relocates the owner-facing page in 022)                                                                                                                                                                                                                                        |

## 1. Repository map

| Path                                                                          | Contents                                                         |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `apps/web`                                                                    | Next.js app: routes, components, API client, e2e tests           |
| `packages/ui`                                                                 | Shared UI kit: shadcn primitives, Persian formatting, styles     |
| `packages/eslint-config`, `packages/typescript-config`                        | Shared lint and TS configs                                       |
| `backend/api`                                                                 | FastAPI service: `app/`, `migrations/`, `tests/`, `scripts/`     |
| `backend/api/openapi.json`                                                    | Generated snapshot; never edit by hand                           |
| `deploy/`, `.github/workflows/`, `Dockerfile.*`, `compose.local.yml`, `data/` | Runtime material, CI, images, local stack, gitignored local data |

Do not add a workspace or top-level folder without an ADR. New decisions get the next ADR number;
never renumber existing ADRs.

## 2. Toolchain

- Node 22 + pnpm 11 (`.node-version`); Python 3.12 + uv (`.python-version`). No npm/yarn or pip/Poetry.
- `pnpm-lock.yaml` and `uv.lock` are authoritative: `pnpm install --frozen-lockfile`,
  `uv sync --locked`.
- Never write `latest` into a manifest; confirm a new dependency is needed and not covered by an
  existing dependency or the stdlib.

## 3. Architecture boundaries

### Backend

Dependency flow: `api/routes → services → repositories → database`.

- Routes parse input, call one service, and return the result — no business logic or SQL. Services
  hold business logic; repositories own all SQLAlchemy 2.x queries.
- Pydantic schemas in `app/schemas/` are the only API boundary types; ORM models never leave the
  repository layer.
- Schema changes need Alembic migrations in `migrations/`. `create_all` is allowed only in tests
  and dev seed scripts.
- External APIs (Parsina, dev mirror, competitor pages) live in `app/integrations/`.
  `app/api/dependencies.py` owns DB sessions and auth guards; `app/api/openapi.py` owns shared
  OpenAPI metadata; `app/core/` owns config, engine/session, security, rate limiting, migration
  lock/runner, role provisioning, and the scheduler. Import public names from `__init__.py`.
- Catalog sync soft-deactivates missing products (never hard-deletes);
  `competitor_listings.product_id` is `ON DELETE RESTRICT`.

### Frontend

- `packages/ui` holds generic, reusable UI. No business logic, no API calls, no app routes.
- `apps/web/components/` holds app-level composites (sidebar, header, theme, settings).
- `apps/web/app/**/_components/` holds components private to one route segment.
- `apps/web/lib/` holds the API client, auth helpers, and app domain helpers.
- Keep data fetching out of presentational components.

### Environments

Charsooq has exactly three independent environments
([ADR 011](docs/adr/011-three-environment-architecture.md)).

| Environment | Host                                 | Frontend / Backend / Database            |
| ----------- | ------------------------------------ | ---------------------------------------- |
| Development | Developer MacBook                    | Next.js / FastAPI / local PostgreSQL     |
| Staging     | Cloud                                | Vercel / FastAPI Cloud / Neon            |
| Production  | Ubuntu `market-linux` (`172.30.2.2`) | Next.js / FastAPI / PostgreSQL in Docker |

- `APP_ENV` is behavior (`development` locally, `production` in Staging and Production);
  `DEPLOYMENT_ENV` is the identity and is mandatory under `APP_ENV=production`. Protected database
  scripts fail closed when it is missing or unknown. Staging is for verification only; keep its
  Vercel/FastAPI Cloud/Neon stack until an approved replacement exists.
- Every environment owns its variables, secrets, and `DATABASE_URL`. Never share them or put real
  values in Git, docs, or `.env.example`. Secrets are file-backed outside the repo (default
  `/etc/charsooq/secrets`), never baked into images; never enter Production credentials in Swagger.
- Production pins the exact PostgreSQL minor (`postgres:19.0-trixie`); Development and CI follow
  the same major. A major bump is a data migration with a rehearsal, never only an image-tag change
  ([ADR 028](docs/adr/028-postgresql-19-upgrade-readiness.md)).
- Migrations run only against the environment's own database via the locked runner
  (`backend/api/scripts/migrate.py`, `MIGRATION_DATABASE_URL`). Production order: secrets/config →
  DB reachability → migration → verify → explicit owner bootstrap if needed → API with
  `RUN_MIGRATIONS_ON_STARTUP=false` and `RUN_OWNER_BOOTSTRAP_ON_STARTUP=false` → `/health`, `/ready`.
  Never start the API before the schema is at `head`; no auto-migrate or auto-bootstrap in Production.
- No automatic Production → Staging/Development data flow; real data outside Production requires a
  controlled, sanitized process. `compose.local.yml` is the hot-reloading development stack;
  Production uses `compose.production.yml`, with only the reverse proxy publishing host ports.
- `main` is not a release. After Staging approval: a version tag → CI + published images → GitHub
  Release → operator runs `make prod-deploy` (locally or with `SSH_HOST=...`): single-slot,
  digest-pinned, health-gated, no runner, no Blue-Green, no untrusted workflow on the host
  ([ADR 018](docs/adr/018-simple-production-deploy.md),
  [ADR 019](docs/adr/019-release-publication-after-image-verification.md)). The Release workflow
  publishes the GitHub Release last, only after both images are built and verified, with the final
  digests in its body — never a placeholder body waiting for a later build.
- With explicit Production identity, both database URLs must be PostgreSQL on **non-loopback**
  hosts with **different roles**; localhost/SQLite fail before connecting. Never print a database
  URL, host, username, or password.
- Production DB roles: administrative (only `db`/`provision`), migration, application (DML only, no
  schema/role privileges). No `docker-entrypoint-initdb.d` provisioning. Verify a backup before any
  destructive migration; no target removes the data volume.
- Rate-limit login to 10/min per IP and username (shared across replicas only with `REDIS_URL`).
  The API never sets HSTS — Caddy owns it in Production, the Vercel edge in Staging.
- Unknown infrastructure details are open, not guesses: registry/promotion, deploy access, migration
  control, secrets, backup/DR, monitoring, Staging data policy, Production seeding. IT owns DNS, CA
  and root-CA distribution, the approved IP (`172.30.2.2` is **not** approved), ports 80/443, IPv6,
  Docker pools, firewall/VLAN, and certificate SAN/renewal.

## 4. UI system

- shadcn/ui only: use official components and Blocks first, style with Tailwind CSS 4. No other
  component library without an ADR. Main sidebar uses the shadcn Sidebar / Block approach.
- `packages/ui` holds generic reusable UI; it must not import from `apps/web`.
- Popups and overlays use the shared primitive in `packages/ui`, never a per-feature override:
  surface `rounded-2xl bg-popover ring-1 ring-foreground/10` plus the standard shadow, items
  `rounded-xl` with `SelectContent`/`SelectItem` spacing. Verify radius, border, shadow, and RTL
  alignment in the browser after touching a menu primitive.
- Center with flex on the element directly wrapping the content; never let a parent center a lone
  inline-level child (`inline-flex`, `inline-block`, `svg`) — baseline alignment shifts it upward.
  Verify visually after changing a button, badge, tab, or row.

## 5. RTL and fonts

- Root document uses `lang="fa"` and `dir="rtl"`. Design for RTL, not only text alignment: use
  logical properties (`margin-inline`, `padding-inline`, `inset-inline-*`, `start`/`end`), no LTR
  hacks unless technically required. Check drawers, dialogs, dropdowns, tables, navigation, icons,
  and alignment in RTL.
- Main UI font: **IRANYekanX**, defined only in `apps/web/app/fonts.ts`. Do not substitute another
  Persian font while it is available.
- Toman glyph: every **visible** Toman unit in the UI must be rendered through `<TomanGlyph />` in
  `packages/ui` (`<Price />` already uses it), including input suffixes, badges, and table cells.
  The component renders `تومانءء`: the two trailing hamzas are required by IRANYekanX's `rlig`
  ligature that produces the `tomaan` glyph — plain `تومان` does **not** activate the glyph.
  Never write the ligature string or copy glyph markup into features; `.toman-glyph` is the only
  font hook (it resolves to IRANYekanX via `--font-sans`; an optional `--font-toman` override belongs
  once in `apps/web/app/fonts.ts`, not in features). Accessible text (`aria-label`, `sr-only`) stays
  plain `تومان` so screen readers announce the unit, not the hamzas
  ([ADR 004](docs/adr/004-persian-formatting.md)).

## 6. Numbers, dates, currency

Machine and display representations are separate.

- **Machine values** (backend, API, calculations, database): plain numbers such as `1000000`,
  integer toman, UTC datetimes. Never store Persian digits or Jalali strings.
- **Display values** (UI only), all implemented in `packages/ui/src/lib/`:
  - Digits: Persian `۰–۹`.
  - Thousands separator: `٬` (U+066C). Example: `۱٬۰۰۰٬۰۰۰`. Never `,`.
  - Dates: Jalali calendar with `٫` (U+066B) as the separator. Example: `۱۴۰۵٫۰۵٫۰۵`. Never
    `/`, `-`, or `.`.
  - Currency: تومان. Use `<Price value={…} />` with the numeric source value; for a standalone
    Toman unit, use `<TomanGlyph />`.

Do not write digit conversion, date formatting, or raw `تومان` strings in feature files.

## 7. Authentication and security

This is an admin panel with password login.

- Hash passwords with Argon2id (`argon2-cffi`); minimum 8 characters. Never store or log plaintext.
- Use opaque server-managed sessions (only a SHA-256 hash is stored) in an HttpOnly cookie: `Secure`
  in production, `SameSite=Lax`, `Path=/`, rotated on every login so older cookies stop working.
- Roles: `owner` (env-managed via `OWNER_*`), `admin` (shop data plus viewer management), `viewer`
  (read-only). Reads use `require_user`; all writes plus `/users*` and `/settings*` use
  `require_admin`; viewers get `403 forbidden`. The owner cannot be deleted and the last management
  account cannot be removed.
- Rate-limit login to 10/min per IP and username. No auth tokens in `localStorage`/`sessionStorage`;
  never log passwords, session IDs, API keys, secrets, or Authorization headers.
- Never commit secrets. Only per-app `.env.example` files (`backend/api/`, `apps/web/`) are tracked;
  `.dockerignore` excludes `.env*` from images. Keep secrets and `DATABASE_URL` per environment;
  never load Production data into non-production automatically. Dev-only defaults are fine;
  Production seeding needs `OWNER_PASSWORD` explicitly (legacy `ADMIN_PASSWORD` alias accepted).

## 8. Coding standards

### TypeScript

- `strict` mode, inherited from `@workspace/typescript-config`.
- No `any` unless unavoidable, with a comment explaining why.
- Explicit, narrow types. Keep components focused and business logic out of presentational ones.

### Python

- Type hints on all functions. Pyright runs in `strict` mode.
- Small, focused functions. Ruff handles lint and format (line length 100).
- Do not catch broad `Exception` to hide errors.

### All code

- Match the surrounding file's naming, comment density, and idiom.
- Do not refactor unrelated code in a focused change.

## 9. Task tracking

For any multi-step task, keep an explicit todo list of small, concrete steps that reflects ground
truth at all times, including right before the final response.

## 10. Motion performance (sidebar + theme)

Glass header and square grid are design requirements — optimize around them, never remove them.
[ADR 007](docs/adr/007-sidebar-theme-motion-performance.md) records the root causes; re-check it
before touching header blur, grid placement, sidebar duration, or global transitions.

- Glass header: translucent + blurred, `isolate`, blur radius at most `backdrop-blur-md`.
- Grid: `.bg-grid-pattern` lives on one dedicated absolute, non-scrolling layer inside
  `SidebarInset`; never on an animating or scrolling container.
- Sidebar: one shared `--sidebar-transition-duration` (≤220ms); the panel transitions only
  `transform`, never `left`/`right`/`width`. Keep gap, panel, and inset durations in sync.
- Close fades labels/icons immediately; open delays the fade-in by ~80ms. Never delay the slide.
- No `transition-all` (list animated props only), no permanent `will-change`, no
  `background-attachment: fixed`. Keep `disableTransitionOnChange` on the theme provider.
- Window rows in huge lists with `use-windowed-rows`; `content-visibility` does not apply to
  `<tr>`/`<tbody>`.

## 11. HTTP API contract

- Base path `/api/v1`; the FastAPI app is the source of truth. Swagger at `/docs`, ReDoc at
  `/redoc`, live document at `/openapi.json`.
- Errors always use `{"error": {"code", "message", "details?"}}`: `code` is stable and
  machine-readable, `message`/`details` are Persian. Responses carry machine values (integer
  Toman, UTC datetimes, ISO dates); all formatting is UI-only.
- Auth: one session per admin. A new login rotates the server-side session, invalidating older
  cookies. Missing or expired sessions return `401 unauthorized`.
- Pagination: `page` starts at 1; `page_size=0` means show all (cap 2000), explicit sizes cap at 500.
  `GET /categories` and `GET /products/groups` send a weak `ETag` and
  `Cache-Control: private, max-age=60`.
- Sync triggers return `202` immediately; counters and errors arrive through the matching
  `GET …/status` endpoint.
- CSV exports are the deliberate exception to machine values: UTF-8 with BOM, comma-separated,
  Persian digits/Jalali dates, capped at 50,000 rows (`409 export_too_large`). Any signed-in
  account may download them.
- After any route or schema change regenerate the committed snapshot:
  `uv run --project backend/api python backend/api/scripts/export_openapi.py`. `make openapi-check`
  (part of `make check` and CI) must pass; never edit `backend/api/openapi.json` by hand.
- `apps/web/lib/api.ts` and `apps/web/lib/api-types.ts` mirror the contract manually — update both
  sides in the same change and run `make typecheck`.

## 12. Checks and tests

- `make check` runs lint, typecheck, both test suites, `make openapi-check`, and `make db-validate`;
  `make build` is the production web build. CI runs the same gates plus Playwright e2e.
- Frontend: `pnpm --filter @workspace/ui test` (Persian digits, `٬` grouping, `٫` Jalali dates,
  `<Price />`); `pnpm --filter web test:e2e` runs against the production build without a backend.
- Backend: `cd backend/api && uv run --no-sync pytest -q` (in-memory SQLite; CI adds PostgreSQL 19).
- Lefthook runs fast checks on commit and broader checks on push. Do not bypass with `--no-verify`
  unless a maintainer asks.

<!-- BEGIN:turborepo-agent-rules -->

# This is NOT the Turborepo you know

Turborepo configuration, task behavior, and CLI commands can vary between installed versions and may differ from your training data. Resolve the `turbo` package from this file's directory or relevant workspace; in monorepos, it may not be visible from the repository root. For example, run `node -p "require.resolve('turbo/package.json')"` from a workspace that depends on `turbo`.

Read `docs/README.md` inside that installed package first, then read the relevant pages from its `docs/` directory before changing Turborepo configuration or commands. Heed deprecation notices. These bundled docs match the installed package version and are available without network access.

This block is written and re-added by `turbo` before repository-scoped commands when an AI agent is detected. In the Turborepo source repository, its template is defined in `crates/turborepo-cli/src/cli/agent_guidance.rs`. Removing the managed block while updates are enabled means a later qualifying invocation will add it again. Set `"agentGuidance": false` in the root `turbo.json` or `turbo.jsonc` to opt out; this does not remove an existing block. Keep the block committed with your work to avoid an uncommitted change on the next agent invocation.
<!-- END:turborepo-agent-rules -->
