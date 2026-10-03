# چهارسوق — Project Specification & Development Guidelines

## 1. Project Overview

**چهارسوق (Charsooq)** is a Persian, RTL-first admin web application intended to be built as a modern, production-ready product.

The project must be designed for long-term maintainability, scalability, security, developer experience, and clear documentation. Architecture and engineering quality are first-class requirements alongside product functionality and visual quality.

The codebase must avoid unnecessary complexity, temporary hacks, duplicated abstractions, and dependencies that do not provide clear value.

---

## 2. Core Technology Stack

### Frontend

- Next.js — current stable version compatible with the project
- React
- TypeScript with strict mode
- Tailwind CSS
- shadcn/ui
- shadcn Blocks
- pnpm
- ESLint
- Prettier

### Backend

- FastAPI — current stable version compatible with the project
- Python
- Pydantic
- SQLAlchemy 2.x
- Alembic
- uv
- Ruff
- Pyright or an equivalent strict Python type checker
- pytest

### Database

- PostgreSQL — current stable major version appropriate for production

---

## 3. Version Policy

Keeping the project technologically up to date is important.

At project initialization and during upgrades:

1. Check official documentation and release information for the involved technologies.
2. Prefer the latest **stable** and mutually compatible versions.
3. Do not use beta, RC, nightly, canary, or experimental releases for core dependencies unless there is an explicit project-level reason.
4. Pin or constrain dependency versions intentionally and commit lockfiles.
5. Keep `pnpm-lock.yaml` and `uv.lock` under version control.
6. Do not blindly use `latest` dependency ranges in committed manifests.
7. Before a major upgrade, verify framework, package, build, test, and runtime compatibility.
8. Prefer official documentation over third-party tutorials when resolving version-specific behavior.

The goal is **modern + reproducible**, not merely “latest”.

---

## 4. Package Management Rules

### JavaScript / TypeScript

Use **pnpm only**.

Do not use npm or yarn for project dependency management.

Use pnpm workspaces for the monorepo.

### Python

Use **uv only**.

Do not use pip, Poetry, Pipenv, or another package manager for project dependency management.

Use:

```bash
uv add <package>
uv remove <package>
uv sync
uv run <command>
```

Keep the Python dependency graph reproducible through `uv.lock`.

---

## 5. Monorepo Architecture

The repository must be a monorepo from the beginning.

Recommended baseline:

```text
charsooq/
├── apps/
│   └── web/
│
├── packages/
│   ├── ui/
│   ├── config/
│   └── eslint-config/
│
├── backend/
│   └── api/
│
├── docs/
│   ├── architecture/
│   ├── adr/
│   └── api/
│
├── scripts/
│
├── .github/
│   └── workflows/
│
├── .lefthook/
│
├── package.json
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── turbo.json
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── README.md
├── CONTRIBUTING.md
└── AGENTS.md
```

Do not create packages or workspaces without a real architectural reason.

A task runner such as Turborepo may be used if it improves monorepo orchestration, caching, and task execution without adding unnecessary complexity.

---

## 6. Project Initialization

Initialize the UI application using the specified shadcn command:

```bash
pnpm dlx shadcn@latest init --preset bIkeymG --template next --monorepo --rtl --pointer
```

Do not replace this initialization approach unless there is a clear compatibility or project requirement.

---

## 7. Design System

The project must use **shadcn/ui + Tailwind CSS** as its primary design system.

Prefer existing shadcn components and official shadcn Blocks over custom-built equivalents.

Use shadcn components for, where applicable:

- Sidebar
- Navigation
- Header
- Cards
- Buttons
- Inputs
- Form controls
- Dialogs
- Sheets
- Dropdown menus
- Selects
- Tabs
- Tables
- Pagination
- Calendar
- Command menu
- Tooltip
- Toast / feedback
- Skeletons
- Empty states
- Error states

Do not build a custom component that duplicates an existing shadcn primitive without a clear reason.

---

## 8. Sidebar

The main admin sidebar must be based on **shadcn Sidebar / shadcn Blocks**.

Requirements:

- RTL-aware
- Responsive
- Full and collapsed desktop states where appropriate
- Mobile drawer/sheet behavior
- Clear active-route state
- Extensible navigation structure
- Keyboard accessible
- Consistent spacing and typography

Suggested structure:

```text
لوگو / چهارسوق

داشبورد

مدیریت
  ├── ...
  ├── ...
  └── ...

گزارش‌ها

تنظیمات

──────────────

حساب مدیر
خروج
```

---

## 9. Persian / RTL Requirements

The application is Persian-first and must use RTL as a foundational design decision.

Use:

```html
<html lang="fa" dir="rtl">
```

Requirements:

- All primary UI copy is Persian unless a technical term must remain in English.
- All layout, alignment, spacing, icons, navigation, forms, tables, and overlays must behave correctly in RTL.
- Prefer CSS logical properties over hard-coded `left` / `right` assumptions.
- Do not “fake” RTL by only changing text alignment.
- Use locale-aware formatting consistently.

---

## 10. Fonts

### Primary UI Font

Use **IRANYekanX** as the primary application font.

The font files will be provided by the project owner.

After receiving the files:

- Register the required weights correctly.
- Define reliable font-weight mapping.
- Load fonts locally in the application.
- Use appropriate fallbacks.
- Keep font loading performant.
- Ensure the font is used consistently across the complete design system.

### Toman Glyph Font

The project will also provide a **Toman Glyph font**.

Use this glyph font for the تومان currency symbol/glyph wherever the product requires the dedicated تومان glyph.

The implementation must centralize this behavior in a reusable component instead of scattering raw font characters throughout the UI.

Recommended interface:

```tsx
<Price value={1250000} />
```

The `Price` component is responsible for formatting the amount and rendering the تومان glyph correctly.

The implementation must also verify that the supplied glyph font contains the required characters and separators needed by the Persian number system defined below.

---

## 11. Persian Number System

This project has a strict separation between **display formatting** and **business/data values**.

### UI

All user-visible numeric digits must be Persian digits:

```text
0123456789
```

must render as:

```text
۰۱۲۳۴۵۶۷۸۹
```

### Backend / API / Database

Backend code, API payloads, business logic, database values, and calculations must continue to use standard numeric values and machine-readable date/time representations.

Never store Persian digits as the canonical numeric representation.

### Centralized formatting

Create shared utilities/components such as:

```text
packages/ui/src/lib/
├── locale.ts
├── number.ts
├── currency.ts
├── date.ts
└── jalali.ts
```

Examples:

```ts
formatPersianNumber(value)
formatCurrency(value)
toPersianDigits(value)
formatPersianDate(value)
```

Do not implement ad-hoc number conversion inside individual components.

---

## 12. Thousand Separator

All grouped amounts and other grouped numeric values shown in the UI must use the Persian thousands separator:

**U+066C ARABIC THOUSANDS SEPARATOR** (`٬`)

Example:

```text
۱٬۰۰۰٬۰۰۰
```

Do not use the Western comma in the Persian UI:

```text
1,000,000
```

The formatting layer must convert machine-readable values into the required Persian display representation.

---

## 13. Currency — Toman

All monetary values in the product are **تومان**.

Database and backend values must remain numeric.

Example canonical value:

```text
1000000
```

Example UI value:

```text
۱٬۰۰۰٬۰۰۰ [Toman Glyph]
```

The UI must:

- Use Persian digits.
- Use `٬` as the thousands separator.
- Use the dedicated تومان glyph/font.
- Keep currency formatting centralized.
- Never store the formatted Persian representation as the source value.

Suggested component:

```tsx
<Price value={1000000} />
```

The component must produce a consistent result across tables, cards, forms, summaries, dialogs, and reports.

---

## 14. Persian Dates / Jalali Calendar

All dates visible to end users must use the **Persian Jalali calendar**.

Example required display:

```text
۱۴۰۵٫۰۵٫۰۵
```

The date separator in the UI must be:

**U+066B ARABIC DECIMAL SEPARATOR** (`٫`)

Do not use:

```text
1405.05.05
1405/05/05
1405-05-05
```

for the default Persian date presentation.

### Date architecture

Database/API:

- Use machine-readable, timezone-aware date/time values where appropriate.
- Do not store Jalali-formatted strings as canonical dates.

UI:

- Convert machine-readable values into Jalali/Persian presentation.
- Use Persian month/day names where applicable.
- Keep date parsing and formatting centralized.

Recommended abstractions:

```tsx
<PersianDate value={date} />
<PersianDateTime value={date} />
<PersianDateRange from={from} to={to} />
```

---

## 15. Locale Consistency

All Persian localization rules should live in one shared formatting layer.

At minimum, centralize:

- Persian digits
- Thousands separator `٬`
- Date separator `٫`
- Jalali calendar conversion
- Persian day/month labels
- Currency formatting
- تومان glyph rendering

The UI should not contain inconsistent manual formatting.

---

## 16. Authentication

This application is an admin panel and requires a simple admin-password login flow.

Initial flow:

```text
Admin Login
    ↓
Password verification
    ↓
Authenticated session
    ↓
Admin Dashboard
```

Public registration and OAuth are not required for the first version.

### Security requirements

- Never store plaintext passwords.
- Use a modern password hashing algorithm such as Argon2id.
- Use secure server-managed sessions.
- Prefer an `HttpOnly` session cookie.
- Use `Secure` in production.
- Configure `SameSite` appropriately.
- Add reasonable login rate limiting / brute-force protection.
- Return non-sensitive authentication errors.
- Keep secrets in environment variables.
- Never commit credentials or secrets.

Avoid putting authentication tokens in `localStorage` unless there is a compelling, documented reason.

---

## 17. Backend Architecture

Use a modular FastAPI architecture.

Recommended baseline:

```text
backend/api/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── security.py
│   ├── api/
│   │   ├── router.py
│   │   └── routes/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── repositories/
│   └── dependencies/
├── migrations/
├── tests/
└── pyproject.toml
```

Preferred dependency flow:

```text
Routes
  ↓
Services
  ↓
Repositories
  ↓
Database
```

Do not place business logic directly inside route handlers.

---

## 18. Database Architecture

Use PostgreSQL with SQLAlchemy 2.x and Alembic.

Rules:

- Schema changes must be represented by migrations.
- Use foreign keys and constraints intentionally.
- Create indexes according to real query patterns.
- Enforce important invariants in the database as well as the application when appropriate.
- Avoid N+1 queries.
- Define transaction boundaries clearly.
- Do not use JSON fields as a substitute for a relational model without a documented reason.
- Keep data types native and machine-readable.

---

## 19. API Contract

FastAPI must expose an OpenAPI contract.

Frontend/backend integration should be contract-driven where practical.

Prefer generating or deriving TypeScript API types/client code from the backend contract to reduce type drift.

The frontend should not depend on backend implementation details.

---

## 20. Validation and Error Handling

Both client-side and server-side validation are required.

Error responses should have predictable structures.

UI states should explicitly handle:

```text
Loading
Success
Empty
Error
Unauthorized
Forbidden
Not Found
Validation Error
```

User-facing messages should be clear and Persian where appropriate.

---

## 21. Forms

Forms must:

- Validate on the client.
- Validate again on the server.
- Show clear field-level errors.
- Support keyboard navigation.
- Use proper labels.
- Work correctly in RTL.
- Avoid duplicate validation rules where a shared schema/contract can be reused.

---

## 22. Responsive Design

The application must be mobile-first.

Support at minimum:

- Mobile
- Tablet
- Desktop

The admin dashboard must not simply be a desktop UI scaled down for mobile.

Tables, forms, sidebars, dialogs, filters, and navigation must have intentional responsive behavior.

---

## 23. Accessibility

Accessibility must be considered from the beginning.

At minimum:

- Semantic HTML
- Keyboard navigation
- Visible focus states
- Correct labels
- Appropriate ARIA attributes
- Accessible dialogs/dropdowns
- Sufficient color contrast
- Screen-reader-friendly state/error feedback

---

## 24. Performance

Performance should be considered at architecture level.

### Frontend

- Prefer Server Components where appropriate.
- Use Client Components only when interaction/state requires them.
- Minimize unnecessary JavaScript.
- Optimize images.
- Avoid unnecessary re-renders.
- Use caching intentionally.
- Use dynamic loading when justified.

### Backend

- Optimize queries.
- Use indexes based on actual access patterns.
- Use connection pooling appropriately.
- Paginate large datasets.
- Avoid N+1 queries.
- Introduce caching only where it provides measurable value.

---

## 25. Testing Strategy

Testing should cover behavior rather than chase coverage numbers alone.

### Frontend

- Unit tests where useful
- Integration tests
- E2E tests for critical user flows

### Backend

- Unit tests
- Integration tests
- API tests

Database-backed integration tests should run against PostgreSQL in CI.

---

## 26. Formatting, Linting, and Type Checking

All development tools must be runnable from the repository root.

Frontend examples:

```bash
pnpm lint
pnpm typecheck
pnpm format
pnpm format:check
```

Backend examples:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

Use a single documented command convention and keep scripts consistent between local development and CI.

---

## 27. Git Hooks

Use one Git hook manager suitable for the mixed pnpm + uv monorepo, preferably **Lefthook** unless another tool provides a clear advantage.

### pre-commit

Keep this hook fast and focused on changed/staged content where possible.

Run appropriate checks such as:

- Formatting
- Linting
- Basic type checks where practical
- Staged-file validation

Do not run full production builds on every commit.

### pre-push

Run broader checks such as:

- Frontend lint
- Frontend typecheck
- Backend lint
- Backend typecheck
- Unit/integration tests
- Relevant build checks

The goal is to stop broken code before it reaches the remote repository.

---

## 28. GitHub Actions / CI

GitHub Actions must be configured from the beginning.

At minimum, CI should validate:

```text
Install dependencies
    ↓
Frontend lint
    ↓
Frontend typecheck
    ↓
Frontend tests
    ↓
Backend lint
    ↓
Backend typecheck
    ↓
Backend tests
    ↓
PostgreSQL integration tests
    ↓
Production build
```

Pull Requests should be blocked from merging when required checks fail.

### CI requirements

- Use frozen lockfile installs.
- Cache pnpm and uv dependencies safely.
- Use PostgreSQL service containers for database integration tests.
- Keep workflow permissions minimal.
- Avoid leaking secrets in logs.
- Prefer pinned/controlled action versions.
- Separate lint/test/build concerns where that improves maintainability.

Recommended workflows:

```text
.github/workflows/
├── ci.yml
├── e2e.yml
└── dependency-review.yml
```

---

## 29. Environment Variables

Maintain:

```text
.env.example
.env.local
.env.test
```

Rules:

- `.env.example` must always be current.
- Real secrets must never be committed.
- Server-only secrets must never be exposed to client bundles.
- Environment access should be centralized in configuration modules where practical.

---

## 30. Documentation

Documentation is a core project requirement.

At minimum:

```text
docs/
├── architecture/
│   ├── overview.md
│   ├── frontend.md
│   ├── backend.md
│   ├── database.md
│   ├── authentication.md
│   ├── api.md
│   ├── deployment.md
│   └── testing.md
├── adr/
└── api/
```

The root `README.md` must explain:

- Project purpose
- Architecture
- Tech stack
- Requirements
- Installation
- Development commands
- Environment variables
- Database setup
- Migrations
- Testing
- Build
- Deployment

Documentation must be updated alongside behavior changes.

---

## 31. Architecture Decision Records

Important architectural decisions should be documented as ADRs.

Example:

```text
docs/adr/
├── 001-monorepo.md
├── 002-authentication.md
├── 003-database.md
└── ...
```

ADR documents should capture the problem, decision, alternatives considered, and consequences.

---

## 32. Naming Conventions

### TypeScript

- `camelCase` for variables/functions
- `PascalCase` for components/types/classes

### Python

- `snake_case` for variables/functions/modules
- `PascalCase` for classes

### Database

- `snake_case`

API routes, files, components, services, repositories, and feature names should follow consistent conventions documented by the project.

---

## 33. UI Architecture

Use a layered UI architecture:

```text
Design Tokens
    ↓
shadcn primitives
    ↓
Reusable UI components
    ↓
Feature components
    ↓
Pages / Routes
```

Generic UI components must not depend on business logic.

Examples of reusable project UI:

```text
Price
PersianNumber
PersianDate
PageHeader
DataTable
ConfirmDialog
EmptyState
ErrorState
```

Feature-specific components should live with the corresponding feature.

---

## 34. Persian UX Consistency

The entire product must behave consistently for Persian users.

The following must never vary between screens without a strong product reason:

- RTL behavior
- Persian digits
- Thousands separator `٬`
- Jalali dates
- Date separator `٫`
- تومان formatting
- Toman glyph
- Error message style
- Loading/empty states

---

## 35. Data Tables, Search, Filters

Admin data interfaces should support, where applicable:

- Pagination
- Search
- Filtering
- Sorting
- Empty state
- Loading state
- Bulk actions
- Column visibility
- Responsive behavior

Large datasets must not rely exclusively on client-side pagination.

---

## 36. Security Baseline

Review and enforce, where applicable:

- Secure headers
- Strict CORS policy
- CSRF protection for cookie-based authentication where required
- Rate limiting
- Strong password hashing
- Input validation
- SQL injection protection through safe query mechanisms
- XSS prevention
- Secure cookies
- Secret management
- Dependency security auditing

---

## 37. Observability and Logging

Backend logging should be structured and useful for debugging and operations.

Never log sensitive information such as:

- Passwords
- Session tokens
- API keys
- Secrets
- Authorization headers

Logging behavior should be consistent across local, CI, and production environments.

---

## 38. Local Development Experience

The common development workflow should be executable from the repository root.

Target experience:

```bash
pnpm install
uv sync
pnpm dev
```

A single root-level development command should launch the required application services whenever practical.

Developers should not need to memorize a long sequence of setup commands.

---

## 39. Docker

Provide Docker configuration when it is useful for reproducible environments and deployment.

Possible services:

```text
web
api
postgres
```

Docker should complement native development rather than unnecessarily replacing it.

---

## 40. Definition of Done

A feature is not considered complete until all relevant requirements are satisfied:

- UI implemented
- Backend implemented
- API contract updated
- Validation implemented
- Error handling implemented
- Loading state implemented
- Empty state implemented where relevant
- Responsive behavior verified
- RTL verified
- Persian digits verified
- Persian thousands separator `٬` verified
- Jalali date verified
- Date separator `٫` verified
- Toman formatting verified
- Toman glyph verified
- Tests added/updated
- Lint passes
- Typecheck passes
- Build passes where applicable
- Documentation updated
- Security implications reviewed

---

## 41. Development Principles

### Prefer

- Simple architecture
- Explicit boundaries
- Reusable abstractions with real value
- Type-safe code
- Contract-driven APIs
- Security by default
- Accessibility
- Responsive design
- Consistent Persian UX
- Automated quality checks
- Documentation alongside implementation

### Avoid

- Unnecessary dependencies
- Duplicate components
- Business logic inside UI components
- Business logic inside route handlers
- Unjustified raw SQL
- Uncontrolled `any`
- Hard-coded secrets
- Storing Persian-formatted numbers in the database
- Storing Jalali presentation strings as canonical dates
- RTL hacks
- Repeated manual formatting logic
- Temporary hacks without documentation
- Overengineering before the requirement exists

---

## 42. Decision Priority

When multiple solutions are possible, prioritize:

```text
Correctness
↓
Security
↓
Maintainability
↓
Developer Experience
↓
Performance
↓
Visual polish
```

The project should be both visually strong and technically defensible.

---

## 43. Final Principle

Build چهارسوق as a real product, not a demo.

Every significant technical decision should survive this question:

> If the project becomes significantly larger over the next few years, will this decision still be easy to understand, test, maintain, and defend?

Prefer the simplest architecture that can support the current requirements and the most likely next stage of growth.
