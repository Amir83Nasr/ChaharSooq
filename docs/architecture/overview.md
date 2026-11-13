# Architecture overview — چهارسوق

Persian RTL-first admin panel. Monorepo with a Next.js frontend, FastAPI backend, and PostgreSQL.

```text
apps/web          Next.js (fa/rtl shell, routes, feature components)
packages/ui       shadcn primitives + shared Persian layer (locale/number/currency/date/jalali, Price/PersianNumber/PersianDate)
backend/api       FastAPI (routes → services → repositories → PostgreSQL)
deploy/caddy      Caddy reverse proxy + TLS modes for Production
docs/             architecture notes, ADRs, API contract notes
```

Dependency flow (backend):

```text
Routes → Services → Repositories → Database
```

Persian rule: backend/API/DB carry machine-readable numerics and tz-aware datetimes.
UI converts at render time: Persian digits, `٬` (U+066C) grouping, Jalali dates with `٫` (U+066B), Toman glyph via `<Price/>`.

## Environments

Charsooq has exactly three independent deployment environments:

| Environment | Where                                       | Main services                                          |
| ----------- | ------------------------------------------- | ------------------------------------------------------ |
| Development | Developer MacBook                           | Next.js + FastAPI + local PostgreSQL                   |
| Staging     | Cloud                                       | Vercel + FastAPI Cloud + Neon                          |
| Production  | Ubuntu server `market-linux` (`172.30.2.2`) | Docker Compose: Caddy + Next.js + FastAPI + PostgreSQL |

Each has its own configuration, secrets, and database. `APP_ENV` is application behavior
(Development runs `development`; Staging and Production run `production`), not environment
identity. `APP_ENV=production` requires an explicit `DEPLOYMENT_ENV`; protected database scripts
use the same identity and fail closed when it is missing or unknown. Staging is verified before
Production; a push to `main` is not a Production release. See [deployment.md](deployment.md) and
[ADR 011](../adr/011-three-environment-architecture.md).

Related: [frontend.md](frontend.md), [backend.md](backend.md), [database.md](database.md), [authentication.md](authentication.md), [api.md](api.md), [deployment.md](deployment.md), [testing.md](testing.md),
[ADR 012](../adr/012-internal-reverse-proxy-and-tls.md).
