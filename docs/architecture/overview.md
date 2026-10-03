# Architecture overview — چهارسوق

Persian RTL-first admin panel. Monorepo with a Next.js frontend, FastAPI backend, and PostgreSQL.

```text
apps/web          Next.js (fa/rtl shell, routes, feature components)
packages/ui       shadcn primitives + shared Persian layer (locale/number/currency/date/jalali, Price/PersianNumber/PersianDate)
backend/api       FastAPI (routes → services → repositories → PostgreSQL)
docs/             architecture notes, ADRs, API contract notes
```

Dependency flow (backend):

```text
Routes → Services → Repositories → Database
```

Persian rule: backend/API/DB carry machine-readable numerics and tz-aware datetimes.
UI converts at render time: Persian digits, `٬` (U+066C) grouping, Jalali dates with `٫` (U+066B), Toman glyph via `<Price/>`.

Related: [frontend.md](frontend.md), [backend.md](backend.md), [database.md](database.md), [authentication.md](authentication.md), [api.md](api.md), [deployment.md](deployment.md), [testing.md](testing.md).
