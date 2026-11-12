# Deployment — چهارسوق

Charsooq has exactly three independent environments. This file is the operational source of
truth for what runs where; [ADR 011](../adr/011-three-environment-architecture.md) records the
decision and its rationale.

## Environments at a glance

|                  | Development                                      | Staging                                     | Production                                           |
| ---------------- | ------------------------------------------------ | ------------------------------------------- | ---------------------------------------------------- |
| Runs on          | Developer MacBook                                | Cloud services                              | Internal Ubuntu server `market-linux` (`172.30.2.2`) |
| Frontend         | Next.js dev server                               | Vercel                                      | Next.js in Docker                                    |
| Backend          | FastAPI dev server                               | FastAPI Cloud                               | FastAPI in Docker                                    |
| Database         | Local PostgreSQL (compose, host `:5433`)         | Neon                                        | PostgreSQL managed on `market-linux`                 |
| Purpose          | Daily development, tests, debugging              | Integration checks and release approval     | Live operational data                                |
| Configuration    | `backend/api/.env.local` + `apps/web/.env.local` | Staging variables in Vercel / FastAPI Cloud | Server-side secret source (mechanism open)           |
| Application mode | `APP_ENV=development`                            | `APP_ENV=production`                        | `APP_ENV=production`                                 |
| Release          | Local working tree                               | Built from an approved commit               | Controlled promotion after Staging approval          |

`APP_ENV` is application behavior, not environment identity. It has three values
(`development`, `test`, `production`); `test` is the pytest/CI harness mode, not a fourth
deployment environment. Staging must run in `production` mode so cookies, secret validation,
logging, and sync behavior match Production. The platform/deployment configuration — not a new
`APP_ENV` value — distinguishes Staging from Production.

Staging is not a second production. It is the last verification step before Production and must
use its own secrets, database, and configuration.

## Environment separation rules (fixed)

These rules apply to every deployment, CI/CD change, and operational script:

1. Each environment has its own environment variables, secrets, and configuration.
2. No secret and no `DATABASE_URL` is shared between environments, unless sharing a specific
   service is a deliberate, documented decision.
3. No real secret value enters Git, public documentation, or example files.
4. `.env.example` files contain only variable names and non-secret sample values.
5. A migration runs only against the database of the environment it targets.
6. No automatic transfer of Production data to Staging or Development is allowed.
7. Any use of real data outside Production requires a controlled process and, where needed,
   data sanitization.
8. Production-only changes must not break Development or Staging without a compatibility review.
9. The current Vercel, FastAPI Cloud, and Neon setup is preserved for Staging until a replacement
   is designed and approved.

## Release flow and CI/CD

Target flow:

```text
Development → GitHub / CI → Staging → approval → Production
```

1. Changes are developed and tested in Development.
2. A pull request runs the repository's CI checks (`.github/workflows/ci.yml`): frontend
   lint/format/typecheck/tests, backend checks on PostgreSQL, migration validation
   (fresh upgrade, idempotent re-upgrade, single head, `alembic check`, downgrade/upgrade),
   the production build, and Playwright e2e. `lefthook` runs the same broad checks on push.
3. The approved commit is deployed to Staging and exercised there, including the frontend ↔ API
   integration.
4. After approval, the release is promoted to Production in a controlled, reversible step.
5. Each environment takes its configuration from its own source at deploy time.

### Current state vs target

- The repository has **no deploy workflow**. `ci.yml` verifies code but does not deploy.
- Vercel and FastAPI Cloud deploy from their Git integration for Staging. Whether those
  platforms wait for CI checks is platform configuration, not encoded in this repository; it
  must be verified in both dashboards before treating the flow as gated.
- Production has no pipeline yet. Building one is a required part of making Production live.
- **A push to `main` must never be assumed to be a Production release.** Production promotion is
  a separate, explicit step.

### Artifacts and version traceability

Staging runs on Vercel/FastAPI Cloud; Production will run Docker Compose on `market-linux`. Their
build systems are different, so **do not assume one Docker image digest is usable in both**.
Until that is proven, the release process must still make the version auditable:

- Treat the **Git commit SHA** as the cross-environment release identity. Record the deployed SHA
  for every Staging and Production release.
- Production builds its image once from the approved commit, tags it immutably (for example
  commit SHA plus build number), pushes it to the chosen registry, and deploys that exact image
  **by digest**. Do not rebuild ad hoc on the server, and never deploy an untracked build.
- Record the Staging platform deployment/build identifier and its commit SHA in the release log.
  If a platform exposes an artifact identifier, record it too.
- Verify that the SHA running in Staging is the SHA baked into the Production image (an OCI
  `revision` label or an equivalent build metadata field).
- If a single artifact cannot be shared across the two infrastructures, document the exact
  commit-to-artifact mapping rather than implying digest parity.

## Development

Development runs on the developer's MacBook with the repository's normal tooling. It is
independent of Staging and Production for configuration, secrets, and data.

```bash
make doctor      # toolchain, env files, postgres health, single migration head
make dev-all     # postgres + migrate, then backend :8000 + frontend :3000
make db-validate # offline migration check (no DB): single head + SQL renders
make check       # lint + typecheck + test + db-validate
```

Copy the example env files once:

```bash
cp backend/api/.env.example backend/api/.env.local
cp apps/web/.env.example apps/web/.env.local
```

`compose.yml` is the **development/local stack** (`migrate` + `api` + `web` + `postgres`). Its
`APP_ENV: production` and placeholder `SESSION_SECRET` exist to exercise production-mode behavior
locally; they are not Production configuration. Do not change `compose.yml` for Production and do
not deploy real secrets through it.

```bash
make docker-up   # build + start web (:3000) + api (:8000) + postgres (:5433)
make docker-logs # follow logs
make docker-down # stop
```

The one-shot `migrate` service applies Alembic before `api` starts. Native `pnpm dev` remains the
default development path.

## Staging

Staging uses managed cloud services and is the closest available rehearsal for Production
behavior, not for Production infrastructure.

### Frontend — Vercel (`apps/web`)

Root `vercel.json` pins the monorepo commands (`pnpm install --frozen-lockfile`,
`pnpm --filter web build`, `apps/web/.next`) so Vercel never falls back to npm or a wrong
workspace root.

Required **Staging** environment variables (Vercel dashboard → Project → Settings → Environment
Variables):

| Variable              | Value                                                                         |
| --------------------- | ----------------------------------------------------------------------------- |
| `API_URL_INTERNAL`    | Staging FastAPI origin, e.g. `https://….fastapicloud.dev` (no trailing slash) |
| `NEXT_PUBLIC_API_URL` | Same Staging FastAPI origin (fallback for the rewrite target)                 |

The `build` script runs `scripts/check-vercel-env.mjs` first: a production build with a loopback
API origin fails fast with a clear message instead of shipping a frontend that proxies to itself.
After changing env vars, use Vercel's **Redeploy** (no cache clear needed — a changed env var
already invalidates the build).

Browser calls always hit same-origin `/api/*`; Next rewrites to the API origin, so the session
cookie stays first-party.

### Backend — FastAPI Cloud (`backend/api`)

Deploy with `make deploy-api` (runs `fastapi deploy` from `backend/api`). Set in the FastAPI Cloud
dashboard for the Staging environment, never shared with Production:

- `APP_ENV=production` (production behavior; Staging identity comes from the platform config)
- the Staging Neon `DATABASE_URL`
- a Staging-only `SESSION_SECRET` (at least 32 characters)
- the Staging `CORS_ORIGINS`
- `SESSION_SAMESITE=none` for the split frontend/API hosts

**Migrations are automatic in Staging.** `app/core/migrations.py::upgrade_to_head` runs in the
FastAPI lifespan on every boot (except `APP_ENV=test`), with a short retry for multi-replica
deploy races. This is acceptable for Staging only; it does not satisfy the Production migration
requirements below.

Staging data is demo/staging data. Do not load a Production dump into Staging. The current
controlled helpers for staging are:

```bash
make db-sync-dev-to-staging # upsert dev data into staging Neon + demo prices (manual, confirmed)
make db-seed-demo-staging   # refresh staging demo competitor prices
```

Both read `backend/api/.env.staging` and never delete products or links.

## Production — `market-linux`

Production runs on the internal Ubuntu server `market-linux` (`172.30.2.2`) with Docker Engine
and Docker Compose. The production database is independent and managed on that server. The
`172.30.2.2` address is an internal address; do not assume it is publicly reachable.

Production is **not implemented in this repository yet**. The following is the required design;
anything marked _open_ is an unresolved decision, not an instruction to guess.

### Required topology

- Services: Next.js (`web`), FastAPI (`api`), PostgreSQL, a one-shot migration job, and a reverse
  proxy.
- Use a **separate** `compose.prod.yml` (or an equivalent production compose file). Do not
  repurpose or modify the development `compose.yml` for Production.
- Only the reverse proxy publishes `80`/`443`. PostgreSQL and the API stay on the internal Docker
  network without public host ports. The browser reaches Next.js, and Next.js proxies `/api/*`
  same-origin as in Staging.
- Configuration comes from a server-side secret source. It is independent of Development and
  Staging and is never baked into images, committed, or copied from another environment.
- Keep resource limits and health checks in the production compose file; deploy by immutable
  image digest.

### Migrations

Production migrations must be controlled and ordered:

1. Run the migration as a dedicated one-shot job **before** the new API version starts.
2. Guarantee a single migration runner (a database advisory lock or an equivalent single-flight
   mechanism). Several workers must not race each other.
3. Keep migrations backward compatible with the currently running API during rollout, so a failed
   release can roll back the application.
4. Take a verified backup before destructive or irreversible schema changes.

The current application runs `upgrade head` in its own lifespan on every boot, and `compose.yml`
also has a one-shot `migrate` service. That is convenient for Development and Staging but is
**not** sufficient as the Production control: boot-time migration on multiple replicas can run
concurrently and it couples schema change to process start. Production release stays blocked
until a controlled migration path exists.

### Secrets, network, TLS, backups

- **Secrets:** choose one server-appropriate mechanism (Docker secrets, a root-owned
  `0600` environment file consumed by systemd/compose, or an external secret manager) and document
  it. Never commit secrets; never place them in the repository or in an image. _Mechanism open._
- **Reverse proxy / TLS:** terminate HTTPS at a reverse proxy, redirect HTTP to HTTPS, and use a
  valid certificate for the production domain. Proxy choice, domain, DNS, and certificate
  issuance are _open_.
- **Network exposure:** expose only what Production needs. PostgreSQL is not reachable from
  outside the server. API access is internal behind the proxy unless a concrete requirement says
  otherwise.
- **Backups and recovery:** schedule encrypted backups, store them off the host, define retention,
  and rehearse a restore. RPO/RTO, tooling, retention, and off-site target are _open_.
- **Rollback:** keep the previous image digest available, deploy by digest so rollback is a
  redeploy, and pair schema changes with a database restore policy. Avoid destructive migrations
  without a verified backup.
- **Host access:** restrict SSH and deployment credentials to the people/systems that need them;
  the CI/CD access method (self-hosted runner vs. SSH) is _open_.

### Legacy assumptions that must not leak into Production

Previous documentation called Vercel + FastAPI Cloud + Neon "Production". Under this architecture
that stack is **Staging**. In particular:

- `make db-migrate-prod`, `make db-seed-prod`, `make db-sync-dev-to-prod`, and `.env.production`
  were written for the Neon-era production database. They are **not** validated for the
  `market-linux` deployment and must not be run against it until their target and safety are
  reworked. Keep using them only for the environment they actually point at.
- `DEV_DATABASE_URL` exists so a production-mode app can simulate Parsina from a dev mirror. It
  is acceptable for Staging/Development simulation, but Production must never point it at a
  non-Production database.
- `compose.yml` is a development stack even though it sets `APP_ENV: production`.
- The API's boot-time auto-migration is acceptable for Staging, not for Production.

## Open decisions

These are unresolved and must be decided before Production goes live. Do not infer answers from
this document.

| Area                    | Open question                                                                                                               |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Hosting details         | Is PostgreSQL containerized by Compose or a host-managed service on `market-linux`?                                         |
| Reverse proxy           | Which proxy (Caddy, Nginx, Traefik, …), and who terminates TLS?                                                             |
| DNS / TLS               | Production domain(s), DNS ownership, certificate issuance and renewal.                                                      |
| Secrets                 | Which secret mechanism on Ubuntu, and who can read/rotate it?                                                               |
| Registry                | Which container registry, image retention, and access control?                                                              |
| Artifact promotion      | Can Staging and Production share one artifact, or only a commit SHA mapping?                                                |
| Deploy access           | Self-hosted runner or SSH from CI? Which account and approvals?                                                             |
| Migration control       | Dedicated migration job, advisory lock, and rollout order — plus code changes needed.                                       |
| Backup / DR             | Tooling, schedule, retention, off-site storage, RPO/RTO, restore drills.                                                    |
| Observability           | Logs, metrics, uptime checks, alerting, and error tracking for each environment.                                            |
| Staging identity        | Staging frontend/API domains, Vercel environment scope, and whether Staging tracks `main` or an explicit release candidate. |
| Data policy             | Exact approval and sanitization process for any real data used outside Production.                                          |
| Production data seeding | How the owner account and initial catalog are provisioned without sharing secrets.                                          |

See also [overview.md](overview.md), [backend.md](backend.md), [database.md](database.md), and
[ADR 011](../adr/011-three-environment-architecture.md).
