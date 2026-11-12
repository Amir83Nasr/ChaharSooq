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

- `APP_ENV=production` (production behavior)
- `DEPLOYMENT_ENV=staging` (explicit identity; Staging and Production share `APP_ENV=production`)
- the Staging Neon `DATABASE_URL`
- a Staging-only `SESSION_SECRET` (at least 32 characters)
- the Staging `CORS_ORIGINS`
- `SESSION_SAMESITE=none` for the split frontend/API hosts

**Migrations are automatic in Staging.** `app/core/migrations.py::upgrade_to_head` runs in the
FastAPI lifespan on every boot (except `APP_ENV=test`), under the ChaharSooq PostgreSQL advisory
lock. The lock makes concurrent replicas single-flight; a waiting replica applies a no-op upgrade
after the first one finishes. This is still a Staging convenience, not the Production process.

Staging data is demo/staging data. Do not load a Production dump into Staging. The current
controlled helpers for staging are:

```bash
make db-sync-dev-to-staging # upsert dev data into staging Neon + demo prices (manual, confirmed)
make db-seed-demo-staging   # refresh staging demo competitor prices
```

Both read `backend/api/.env.staging` and never delete products or links. The Make targets set
`DEPLOYMENT_ENV=staging`; the scripts refuse to run with Production or an unknown identity.

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

The repository now implements steps 1–2 as infrastructure, but **does not** yet wire them into a
Production compose file or deployment workflow. The runner is
`backend/api/scripts/migrate.py`:

```bash
DEPLOYMENT_ENV=production uv run --project backend/api \
  python backend/api/scripts/migrate.py
```

It resolves the database through `DatabaseSettings` only, applies Alembic to `head` under the
PostgreSQL session-level advisory lock, and exits non-zero on failure or lock timeout. The same
lock is used by a plain `alembic upgrade head`, because `migrations/env.py` acquires it when it
opens its own connection. When a caller supplies a connection through
`config.attributes["connection"]`, Alembic reuses that exact connection, so the lock and the
migration cannot run on different sessions. See
[database.md](database.md#migrations-and-the-single-runner-lock).

The API still runs `upgrade head` in its own lifespan on every boot in Development and Staging,
and `compose.yml` also has a one-shot `migrate` service. That is convenient there but is **not**
sufficient as the Production control: boot-time migration on multiple replicas couples schema
change to process start. Production sets `RUN_MIGRATIONS_ON_STARTUP=false` (the Production
default) and runs the standalone runner as the ordered pre-start step.

`RUN_MIGRATIONS_ON_STARTUP` and `RUN_OWNER_BOOTSTRAP_ON_STARTUP` are independent and default to
`true` in Development/Staging and `false` in Production. Production **rejects** an explicit `true`
for either flag, so an API boot can never change the schema or provision the owner there. The
explicit owner command is:

```bash
DEPLOYMENT_ENV=production uv run --project backend/api \
  python backend/api/scripts/bootstrap_owner.py
```

That command requires the `admins` table to exist, never calls `create_all`, and is idempotent.
The default owner-on-boot behavior is preserved for Development and Staging. The Production
deployment workflow (who runs these commands, order, and approvals) is still proposed, not
implemented.

### Required Production order

This is the official order for a Production release. It is a policy contract; the compose/release
wiring is still the open item below.

1. Prepare the Production secrets and configuration in the Production-only secret source.
2. Verify the database is reachable from the deployment host.
3. Run `scripts/migrate.py` with `DEPLOYMENT_ENV=production` and the Production secret source.
   Stop the rollout on a non-zero exit, including a lock timeout.
4. Verify the migration succeeded and the database reports the expected revision (`head`).
5. Run `scripts/bootstrap_owner.py` explicitly when the owner needs provisioning or rotation; stop
   on a non-zero exit.
6. Start the API with `RUN_MIGRATIONS_ON_STARTUP=false` and
   `RUN_OWNER_BOOTSTRAP_ON_STARTUP=false` (also the Production defaults).
7. Check `/health` and `/ready` before routing traffic; roll back to the previous image if the
   application check fails. Schema rollback still follows the backup policy.

**The API must never start before the schema is at `head`.** A boot with either startup step
enabled is rejected by configuration, not merely discouraged.

This is the approved ordering for the future Production compose/workflow; it is not an implemented
deploy path yet.

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
  were written for the Neon-era production database. Those targets are now disabled and fail
  closed (see [Protected database commands](#protected-database-commands-phase-0-quarantine)).
  `.env.production` must not be reused for `market-linux`.
- `DEV_DATABASE_URL` exists so a production-mode app can simulate Parsina from a dev mirror. It
  is acceptable for Staging/Development simulation, but Production must never point it at a
  non-Production database.
- `compose.yml` is a development stack even though it sets `APP_ENV: production`. Because runtime
  configuration now requires `DEPLOYMENT_ENV` whenever `APP_ENV=production`, the local container
  stack must also receive `DEPLOYMENT_ENV=development`; wiring that into the compose services is
  pending compose work and is intentionally unchanged in this task.
- The API's boot-time auto-migration is acceptable for Staging, not for Production.

## Protected database commands (Phase 0 quarantine)

Legacy production write paths are blocked until a controlled Production path exists. Environment
identity comes from `DEPLOYMENT_ENV`, not `APP_ENV`: Staging and Production both run
`APP_ENV=production`, so `APP_ENV` cannot distinguish them.

Accepted `DEPLOYMENT_ENV` values are `development`, `staging`, and `production`. The guard lives in
`backend/api/app/core/deployment.py`. It is fail-closed: a missing, empty, or unrecognised value
raises an error, the CLI exits non-zero, and it does so before reading `DATABASE_URL` or opening a
connection. Unknown is never treated as Development.

The Make targets set the identity for the scripts they call:

| Command                                                                                                    | Identity      | Status   |
| ---------------------------------------------------------------------------------------------------------- | ------------- | -------- |
| `make db-migrate`, `db-bootstrap-owner`, `db-seed`, `db-seed-parsina`, `db-seed-demo`, `db-clear-products` | `development` | Allowed  |
| `make db-sync-dev-to-staging`, `db-seed-demo-staging`                                                      | `staging`     | Allowed  |
| `make db-migrate-prod`                                                                                     | —             | Disabled |
| `make db-seed-prod`                                                                                        | —             | Disabled |
| `make db-sync-dev-to-prod` (and the `sync-prod` / `dev-to-prod` aliases)                                   | —             | Disabled |

Disabled targets print the reason and exit non-zero before running any tool. They do not fall back
to a different database.

Script-level rules (these also apply when a script is invoked directly):

| Script                     | Allowed `DEPLOYMENT_ENV` | Reason                                                                                                           |
| -------------------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| `migrate.py`               | all three (explicit)     | Standalone locked migration runner; no `create_all`. Production use requires the approved deployment workflow.   |
| `bootstrap_owner.py`       | all three (explicit)     | Explicit owner path; requires a migrated `admins` table; no `create_all`.                                        |
| `seed_admin.py`            | `development`, `staging` | Also runs `create_all`; Production owner provisioning is an open decision.                                       |
| `seed_parsina_products.py` | `development`            | Loads the development CSV fixture.                                                                               |
| `seed_demo_competitors.py` | `development`, `staging` | Demo data only; Staging additionally requires `--staging`.                                                       |
| `clear_products.py`        | `development`            | Destructive; never Staging or Production.                                                                        |
| `sync_dev_to_prod.py`      | `staging` (destination)  | Called by `db-sync-dev-to-staging`; the historical name and `--prod-url` flag remain, but Production is refused. |

Running a script directly requires the identity explicitly:

```bash
DEPLOYMENT_ENV=development uv run --project backend/api \
  python backend/api/scripts/seed_admin.py
```

### Approved Production paths

There are none yet in the sense of an implemented deployment workflow. In particular:

- The migration **mechanism** exists: `scripts/migrate.py` and the advisory lock. It is not yet
  wired into a Production compose file or a release job; `make db-migrate-prod` remains the
  disabled Neon-era target and is not that step.
- The explicit owner **command** exists: `scripts/bootstrap_owner.py`. Production still needs an
  approved deployment workflow that decides who runs it, when, and with which secret source.
- No data-sync command from Development or Staging into Production is approved.

Until that workflow is approved, Production writes stay blocked rather than relying on an operator
to choose the right database.

## Configuration foundation (implemented)

The repository now contains the configuration primitives Production needs, without implementing
a Production deployment. This section describes implemented behavior; it does not approve a
Production release, migration path, or secret mechanism.

### Settings split

- `DatabaseSettings` (`backend/api/app/core/config.py`) contains `database_url` and
  `migration_lock_timeout_seconds`. The SQLAlchemy engine, `app/core/migrations.py`, and
  `migrations/env.py` use `get_database_settings()`; they no longer instantiate the full
  application model. Database and migration configuration therefore works without authentication
  secrets.
- `Settings` inherits `DatabaseSettings` and adds application behavior: `APP_ENV`, session, owner,
  CORS, sync, `RUN_MIGRATIONS_ON_STARTUP`, and `RUN_OWNER_BOOTSTRAP_ON_STARTUP`. Its public fields
  and consumers are unchanged apart from the new startup switch.
- `ParsinaSettings` remains separate and optional. Its password can come from the environment or a
  secret file and it is not required to boot the API.

### Secret files (`SECRETS_DIR`)

When `SECRETS_DIR` is set, settings read one value per file from that directory. Expected file
names:

| Secret file        | Setting            | Required in Production?                              |
| ------------------ | ------------------ | ---------------------------------------------------- |
| `database_url`     | `DATABASE_URL`     | Yes, must be explicit, PostgreSQL, and non-loopback. |
| `session_secret`   | `SESSION_SECRET`   | Yes (existing production rule).                      |
| `owner_password`   | `OWNER_PASSWORD`   | Yes (existing production rule, minimum 8 chars).     |
| `parsina_password` | `PARSINA_PASSWORD` | No; only when Parsina is configured.                 |

Precedence, highest first:

1. constructor arguments,
2. environment variables,
3. env files (`backend/api/.env.local`, `backend/api/.env`, ...),
4. files under `SECRETS_DIR`.

Environment variables therefore keep their documented precedence. Secret values are not logged or
included in configuration errors. An explicitly set `SECRETS_DIR` must be an existing directory in
every environment; a missing directory fails fast. The planned Production mount location is
`/run/secrets`, but this repository does not create or mount it yet.

When `DEPLOYMENT_ENV=production` is explicit, configuration fails closed if:

- `DATABASE_URL` is missing, resolves to the committed localhost development default, is not a
  PostgreSQL URL, has no explicit host, or targets `localhost`, `127.0.0.0/8`, `::1`, or an
  IPv4-mapped loopback address — including when Alembic runs in offline SQL mode;
- `SESSION_SECRET` is the development default or shorter than 32 bytes;
- `OWNER_PASSWORD` is shorter than 8 characters;
- `RUN_MIGRATIONS_ON_STARTUP` or `RUN_OWNER_BOOTSTRAP_ON_STARTUP` is explicitly `true`.

Database URL validation uses SQLAlchemy's URL parser and inspects libpq-style `host`/`hostaddr`
query parameters; it is not substring matching. Error messages never contain the URL, host,
username, or password. Development and Staging keep their previous compatibility.

A value may come from either the environment or a secret file. If neither supplies it, the error
names the missing setting; a missing file is never mistaken for an intentional Development value.
`parsina_password` stays optional, so a disabled Parsina integration does not block boot.

`DEPLOYMENT_ENV` is mandatory whenever `APP_ENV=production`: Staging and Production share that
application mode, so the process cannot identify itself without it. A missing, empty, or unknown
value raises a configuration error before the database is opened. Development keeps the previous
lenient behavior. Protected database commands continue to require and validate the identity as
described above.

### Startup migrations and owner bootstrap

| Environment | `RUN_MIGRATIONS_ON_STARTUP` | `RUN_OWNER_BOOTSTRAP_ON_STARTUP` |
| ----------- | --------------------------- | -------------------------------- |
| Development | `true`                      | `true`                           |
| Staging     | `true`                      | `true`                           |
| Production  | `false`                     | `false`                          |

An operator's explicit value is preserved, except in Production: an explicit `true` is a
configuration error. The two switches remain independent, and neither weakens the existing
`SESSION_SECRET` and `OWNER_PASSWORD` validation.

Production starts the API only after `scripts/migrate.py` and, when needed,
`scripts/bootstrap_owner.py` succeed, with both flags at `false`. In Development/Staging the
automatic behavior is unchanged: the account is created when missing, re-hashed when the env
password changes, and kept as the only `owner`.

### Advisory lock and single runner

`app/core/migration_lock.py` implements a PostgreSQL **session-level** advisory lock with the fixed
key `int.from_bytes(b"charsooq", "big")` (documented in the module). The lock is held for the whole
Alembic run, released in `finally`, and also released by PostgreSQL when the connection closes if
the process dies. Transaction-level locking is deliberately not used because Alembic commits
between revisions.

`scripts/migrate.py` and the lifespan share the same `apply_migrations()` path. It opens a
short-lived engine, connects, acquires the lock, and passes that connection to Alembic through
`config.attributes["connection"]`. `migrations/env.py` reuses the supplied connection instead of
creating its own; a direct `alembic upgrade head` creates one connection and acquires the same
lock before running. `MIGRATION_LOCK_TIMEOUT_SECONDS` (default 60) bounds the wait, and a timeout
is reported as a clear non-zero failure.

SQLite keeps the previous no-lock Development behavior. An explicitly identified Production
deployment using a non-PostgreSQL dialect fails closed instead of migrating without the lock.

### `SESSION_SECRET` status

`SESSION_SECRET` is validated in production mode but is not currently used to sign or encrypt
session cookies. Sessions are opaque random tokens stored as SHA-256 hashes (`app/core/security.py`
and the auth service). The value is not required by current runtime behavior, but it remains part
of the production security checks. Removing or repurposing it is a separate authentication design
decision; this configuration foundation does not change it.

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
| Migration control       | Production compose/release integration of the locked runner, rollout order, backup gate, and approvals.                     |
| Backup / DR             | Tooling, schedule, retention, off-site storage, RPO/RTO, restore drills.                                                    |
| Observability           | Logs, metrics, uptime checks, alerting, and error tracking for each environment.                                            |
| Staging identity        | Staging frontend/API domains, Vercel environment scope, and whether Staging tracks `main` or an explicit release candidate. |
| Data policy             | Exact approval and sanitization process for any real data used outside Production.                                          |
| Production data seeding | How the owner account and initial catalog are provisioned without sharing secrets.                                          |

See also [overview.md](overview.md), [backend.md](backend.md), [database.md](database.md), and
[ADR 011](../adr/011-three-environment-architecture.md).
