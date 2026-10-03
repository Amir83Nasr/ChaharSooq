# AGENTS.md — چهارسوق

## Purpose

This file contains the repository-level rules for coding agents working on **چهارسوق (Charsooq)**.

Agents must treat these rules as project constraints, not optional suggestions.

---

## 1. Stack and Package Managers

- Frontend: Next.js + React + TypeScript + Tailwind CSS + shadcn/ui.
- Backend: FastAPI + Python + SQLAlchemy 2.x + Pydantic + Alembic.
- Database: PostgreSQL.
- JavaScript package manager: **pnpm only**.
- Python package manager: **uv only**.
- Do not introduce npm, yarn, pip, Poetry, or another package manager for project dependency management.
- Respect existing lockfiles: `pnpm-lock.yaml` and `uv.lock`.
- Prefer current stable, mutually compatible dependency versions.
- Do not blindly replace versions with `latest` in committed manifests.

---

## 2. Repository Structure

The repository is a monorepo.

Prefer the established structure:

```text
apps/web
packages/*
backend/api
docs/*
scripts/*
.github/workflows/*
```

Do not create a new package/workspace without a real reason.

Do not move files between architectural layers casually. Preserve established boundaries unless there is a documented reason to change them.

---

## 3. UI / Design System

- Use **shadcn/ui** as the default UI system.
- Prefer official shadcn components and Blocks over custom equivalents.
- The main sidebar must use the shadcn Sidebar / Block approach.
- Use Tailwind CSS for styling.
- Do not introduce another component library without explicit architectural justification.
- Keep generic UI components independent from business logic.

---

## 4. RTL / Persian-First Rules

The application is Persian and RTL-first.

- Root document must use `lang="fa"` and `dir="rtl"`.
- Design all layouts for RTL, not merely text alignment.
- Prefer CSS logical properties (`margin-inline`, `padding-inline`, `inset-inline-*`, etc.) over hard-coded left/right assumptions.
- Verify drawers, dialogs, dropdowns, tables, navigation, icons, and alignment in RTL.
- Do not add LTR hacks unless a specific technical value requires them.

---

## 5. Fonts

### IRANYekanX

Use the provided **IRANYekanX** font as the main UI font.

Do not silently substitute another Persian font when the provided font is available.

Keep font definitions centralized and map weights correctly.

### Toman Glyph

Use the provided **Toman Glyph font** for the تومان currency glyph.

Do not duplicate the currency glyph logic across components.

Prefer a reusable `Price`/currency component or equivalent abstraction.

The implementation must account for the required Persian numeric characters and separators as defined below.

---

## 6. Persian Number Formatting — REQUIRED

There are two representations:

### Machine representation

Backend, API payloads, calculations, and database values use standard machine-readable numeric values.

Example:

```text
1000000
```

### UI representation

All user-visible numbers use Persian digits:

```text
۱۰۰۰۰۰۰
```

Never store Persian digits as canonical numeric values.

Create and reuse centralized formatting utilities/components. Never implement one-off digit conversion in random UI files.

---

## 7. Thousand Separator — REQUIRED

Use **U+066C ARABIC THOUSANDS SEPARATOR**:

```text
٬
```

Required display example:

```text
۱٬۰۰۰٬۰۰۰
```

Do not use the Western comma for Persian numeric grouping:

```text
1,000,000
```

---

## 8. Persian Date Formatting — REQUIRED

The UI must use the **Jalali/Persian calendar**.

Required example:

```text
۱۴۰۵٫۰۵٫۰۵
```

Use **U+066B ARABIC DECIMAL SEPARATOR**:

```text
٫
```

Do not use Western dot, slash, or hyphen as the default Persian date presentation.

Canonical dates in the backend/database must remain machine-readable and must not be stored as Jalali display strings.

Centralize date conversion and formatting.

---

## 9. Currency — REQUIRED

The project currency is **تومان**.

All prices shown in UI must:

1. Use Persian digits.
2. Use `٬` for thousands grouping.
3. Use the provided تومان glyph font.
4. Keep the source value numeric.

Example source:

```text
1000000
```

Expected UI pattern:

```text
۱٬۰۰۰٬۰۰۰ [Toman Glyph]
```

Do not scatter raw `تومان` strings when the dedicated glyph is required.

---

## 10. API and Backend Boundaries

Prefer this dependency flow:

```text
Route
  ↓
Service
  ↓
Repository
  ↓
Database
```

- Keep business logic out of route handlers.
- Keep database access out of UI code.
- Use Pydantic schemas for API boundaries.
- Use SQLAlchemy 2.x for database access.
- Use Alembic for schema migrations.
- Keep OpenAPI/API contracts up to date.

---

## 11. Authentication / Security

This is an admin panel.

Use a simple but secure admin password authentication flow.

Required principles:

- Never store plaintext passwords.
- Prefer Argon2id or an equally strong modern password hashing algorithm.
- Prefer secure server-managed sessions.
- Prefer HttpOnly cookies for session state.
- Use `Secure` cookies in production.
- Apply appropriate `SameSite` policy.
- Protect login against brute-force attempts/rate-limit abuse.
- Never log passwords, session tokens, secrets, API keys, or authorization headers.
- Never commit secrets.

Do not use `localStorage` for authentication tokens without a documented reason.

---

## 12. Coding Standards

### TypeScript

- Strict mode.
- Avoid `any` unless there is a documented and unavoidable reason.
- Prefer explicit, narrow types.
- Keep components focused.
- Do not mix business logic into presentational components.

### Python

- Use type hints consistently.
- Keep functions small and focused.
- Use Ruff.
- Use strict type checking where configured.
- Do not hide errors with broad exception handling.

---

## 13. Formatting and Quality Commands

All required checks must be runnable from repository root.

Typical commands:

```bash
pnpm lint
pnpm typecheck
pnpm format:check

uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

Use the project's actual scripts/configuration when they exist.

---

## 14. Git Hooks

Use the configured Git hook manager (preferably Lefthook).

### pre-commit

Keep fast:

- staged-file formatting
- linting
- lightweight validation

### pre-push

Run broader checks:

- frontend lint/typecheck
- backend lint/typecheck
- tests
- relevant build checks

Do not weaken hooks just to make a change pass.

---

## 15. GitHub Actions

Every meaningful code change should remain compatible with CI.

CI should cover, where configured:

- frozen pnpm installation
- uv dependency synchronization
- frontend lint
- frontend typecheck
- frontend tests
- backend lint
- backend typecheck
- backend tests
- PostgreSQL integration tests
- production build

Keep workflow permissions minimal and avoid leaking secrets.

---

## 16. Testing Rules

When changing behavior, update or add relevant tests.

Prioritize:

- critical user flows
- authentication
- money formatting
- Persian number formatting
- Jalali date formatting
- API validation
- database behavior
- error states

Do not claim a feature is complete when its relevant tests are absent or failing.

---

## 17. Documentation Rules

Documentation is part of implementation.

When changing architecture, API behavior, setup, commands, environment variables, or user-visible rules:

- update the relevant docs
- update README/CONTRIBUTING when needed
- add/update an ADR for significant architectural decisions

Keep documentation close to the codebase and current.

---

## 18. Change Discipline

Before editing code:

1. Inspect the current implementation and project structure.
2. Reuse existing abstractions/components when appropriate.
3. Check related tests and documentation.
4. Understand the data/API flow before changing it.

After editing:

1. Run the narrowest relevant checks first.
2. Run broader checks before considering the task complete.
3. Review the diff for accidental changes.
4. Update documentation if behavior/architecture changed.

Do not make unrelated refactors while implementing a focused task unless they are required to safely complete it.

---

## 19. Dependency Discipline

Before adding a dependency, verify:

- the need is real
- the standard library or existing dependency cannot solve it cleanly
- the package is maintained
- it supports the current stack
- it does not introduce avoidable bundle/runtime cost
- it does not create unnecessary lock-in

Prefer fewer dependencies and clearer code.

---

## 20. Persian UI Acceptance Checklist

Before declaring a UI task complete, verify:

- [ ] RTL works correctly
- [ ] IRANYekanX is used
- [ ] All visible digits are Persian
- [ ] Thousands grouping uses `٬`
- [ ] Dates are Jalali
- [ ] Date presentation uses `٫`
- [ ] Prices are in تومان
- [ ] Toman glyph is used where required
- [ ] Backend/database values remain machine-readable
- [ ] Loading state exists where necessary
- [ ] Empty state exists where necessary
- [ ] Error state exists where necessary
- [ ] Mobile/tablet/desktop behavior is intentional
- [ ] Keyboard accessibility works

---

## 21. Definition of Done

A task is done only when:

- implementation is complete
- relevant tests pass
- lint/typecheck pass
- formatting passes
- CI expectations are satisfied
- responsive behavior is verified
- RTL behavior is verified
- Persian localization rules are verified
- documentation is updated when required
- no secrets or unrelated changes are introduced

---

## 22. Final Agent Principle

Build the simplest solution that satisfies the requirement and fits the existing architecture.

Do not optimize for cleverness.
Do not optimize for the shortest code.
Do not optimize for adding more libraries.

Optimize for:

```text
Correctness
Security
Maintainability
Consistency
Developer Experience
Performance
```

Treat چهارسوق as a long-lived production project.

<!-- BEGIN:turborepo-agent-rules -->

# This is NOT the Turborepo you know

Turborepo configuration, task behavior, and CLI commands can vary between installed versions and may differ from your training data. Resolve the `turbo` package from this file's directory or relevant workspace; in monorepos, it may not be visible from the repository root. For example, run `node -p "require.resolve('turbo/package.json')"` from a workspace that depends on `turbo`.

Read `docs/README.md` inside that installed package first, then read the relevant pages from its `docs/` directory before changing Turborepo configuration or commands. Heed deprecation notices. These bundled docs match the installed package version and are available without network access.

This block is written and re-added by `turbo` before repository-scoped commands when an AI agent is detected. In the Turborepo source repository, its template is defined in `crates/turborepo-cli/src/cli/agent_guidance.rs`. Removing the managed block while updates are enabled means a later qualifying invocation will add it again. Set `"agentGuidance": false` in the root `turbo.json` or `turbo.jsonc` to opt out; this does not remove an existing block. Keep the block committed with your work to avoid an uncommitted change on the next agent invocation.
<!-- END:turborepo-agent-rules -->
