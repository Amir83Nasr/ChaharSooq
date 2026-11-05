# AGENTS.md

Constraints for coding agents on **چهارسوق (Charsooq)**, a Persian, RTL-first admin panel. Setup: [README.md](README.md). Contribution flow: [CONTRIBUTING.md](CONTRIBUTING.md). Architecture: [docs/](docs/README.md).

## 1. Repository map

| Path                                                   | Contents                                                            |
| ------------------------------------------------------ | ------------------------------------------------------------------- |
| `apps/web`                                             | Next.js app: routes, app-level components, API client, e2e tests    |
| `packages/ui`                                          | Shared UI kit: shadcn primitives, Persian formatting, global styles |
| `packages/eslint-config`, `packages/typescript-config` | Shared ESLint and TypeScript configs                                |
| `backend/api`                                          | FastAPI service: `app/`, `migrations/`, `tests/`, `scripts/`        |
| `backend/api/openapi.json`                             | Committed OpenAPI snapshot. Generated; never edit by hand           |
| `docs/`                                                | Architecture notes, ADRs, API notes                                 |
| `.github/workflows/`                                   | CI and deploy                                                       |
| `Dockerfile.*`, `compose.yml`                          | Container images and the local stack                                |
| `data/`                                                | Local-only data files (gitignored)                                  |

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

## 9. Task tracking

- For any multi-step task, maintain an explicit todo list with small, concrete steps.
- Keep it continuously updated: mark a step in-progress when starting it, completed right after finishing it, and add newly discovered steps immediately.
- The list must reflect ground truth at all times, including at the very end of the task — update it before the final response.

## 10. Motion performance (sidebar + theme)

Desktop toggle/theme lag was caused by repainting the glass header and the
grid together on every animation frame, plus layout-driven transitions.
Glass (`backdrop-blur` header) and the square grid background are kept by
design — optimize around them, never remove them:

- Glass header: keep it translucent + blurred, with `isolate` so the blur
  stays in its own stacking context. Do not raise the blur radius above
  `backdrop-blur-md`.
- Grid: never put `.bg-grid-pattern` on an animating or scrolling container
  (`SidebarInset`, scroll divs). It lives on one dedicated absolute,
  non-scrolling layer inside `SidebarInset` (see
  `apps/web/app/(dashboard)/layout.tsx`).
- Sidebar motion: one shared duration/easing (`--sidebar-transition-duration`,
  currently 220ms — keep it at 220ms or less). The sliding panel transitions
  only `transform`; never `left`/`right`/`width` on it. Keep gap, panel, and
  inset durations in sync.
- Staged choreography (pure CSS, direction-dependent delays — transitions
  read params from the NEW state): the collapsed rules fade labels/icons
  fast with no delay (close leads with content vanishing), the base rules
  delay the fade-in by 80ms (open trails: panel slides + content shrinks
  first). Total stays ~220ms. Never add a delay to the slide/push itself.
- Never use `transition-all`. List only the animated props
  (e.g. `transition-[transform,opacity]`,
  `transition-[color,background-color,border-color,box-shadow,opacity]`).
- No permanent `will-change` hints. The compositor promotes the transform
  slide while it runs; standing hints pin layers and make the blurred
  header more expensive.
- Keep `disableTransitionOnChange` on the next-themes provider so a theme
  flip never animates every element.
- Never add `background-attachment: fixed` to grid/glass surfaces.
- Huge lists ("show all" renders the whole catalog): window the rows
  (`use-windowed-rows` — viewport slice + overscan + spacers, measured
  heights, no new dependency). `content-visibility` does NOT apply to
  `<tr>`/`<tbody>` (internal table boxes), so it can't fix table jank.
- Root-cause record: [ADR 007](docs/adr/007-sidebar-theme-motion-performance.md)
  — re-check it before touching header blur, grid placement, sidebar
  duration, or global transitions.

<!-- BEGIN:turborepo-agent-rules -->

# This is NOT the Turborepo you know

Turborepo configuration, task behavior, and CLI commands can vary between installed versions and may differ from your training data. Resolve the `turbo` package from this file's directory or relevant workspace; in monorepos, it may not be visible from the repository root. For example, run `node -p "require.resolve('turbo/package.json')"` from a workspace that depends on `turbo`.

Read `docs/README.md` inside that installed package first, then read the relevant pages from its `docs/` directory before changing Turborepo configuration or commands. Heed deprecation notices. These bundled docs match the installed package version and are available without network access.

This block is written and re-added by `turbo` before repository-scoped commands when an AI agent is detected. In the Turborepo source repository, its template is defined in `crates/turborepo-cli/src/cli/agent_guidance.rs`. Removing the managed block while updates are enabled means a later qualifying invocation will add it again. Set `"agentGuidance": false` in the root `turbo.json` or `turbo.jsonc` to opt out; this does not remove an existing block. Keep the block committed with your work to avoid an uncommitted change on the next agent invocation.
<!-- END:turborepo-agent-rules -->
