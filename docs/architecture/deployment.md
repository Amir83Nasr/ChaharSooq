# Deployment — چهارسوق

Charsooq has exactly three independent environments. This file is the operational source of
truth for what runs where; [ADR 011](../adr/011-three-environment-architecture.md) records the
decision and its rationale.

## Environments at a glance

|                  | Development                                      | Staging                                     | Production                                           |
| ---------------- | ------------------------------------------------ | ------------------------------------------- | ---------------------------------------------------- |
| Runs on          | Developer MacBook                                | Cloud services                              | Internal Ubuntu server `market-linux` (`172.30.2.2`) |
| Frontend         | Next.js dev server                               | Vercel                                      | Next.js in Docker (`web`)                            |
| Backend          | FastAPI dev server                               | FastAPI Cloud                               | FastAPI in Docker (`api`)                            |
| Database         | Local PostgreSQL (compose, host `:5433`)         | Neon                                        | PostgreSQL 18.6 in Docker (`db`)                     |
| Purpose          | Daily development, tests, debugging              | Integration checks and release approval     | Live operational data                                |
| Configuration    | `backend/api/.env.local` + `apps/web/.env.local` | Staging variables in Vercel / FastAPI Cloud | `/etc/charsooq/secrets` (file-backed) + compose file |
| Application mode | `APP_ENV=development`                            | `APP_ENV=production`                        | `APP_ENV=production`, `DEPLOYMENT_ENV=production`    |
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

Staging runs on Vercel/FastAPI Cloud; Production runs Docker Compose on `market-linux`. Their
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

`compose.yml` is the **development/local stack** (`migrate` + `api` + `web` + `postgres`). It sets
`APP_ENV=production` to exercise production application behavior locally and
`DEPLOYMENT_ENV=development` so runtime configuration and migration scripts never treat it as
Production. Its session and owner values are development placeholders, not Production
configuration. Do not change `compose.yml` for Production and do not deploy real secrets through it.

```bash
make docker-up   # build + start web (:3000) + api (:8000) + postgres (:5433)
make docker-logs # follow logs
make docker-down # stop
```

The one-shot `migrate` service runs the locked `scripts/migrate.py` before `api` starts. Native
`pnpm dev` remains the default development path. Development keeps its existing single-role
`charsooq` database and has no provisioning service; `MIGRATION_DATABASE_URL` is optional and
migrations fall back to `DATABASE_URL`. Role separation is a Production requirement, not a
Development one.

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
- the Staging Neon `DATABASE_URL` (application role)
- optionally `MIGRATION_DATABASE_URL` (migration role); when absent, Staging migrations fall back to
  `DATABASE_URL`, preserving the previous single-URL behavior
- a Staging-only `SESSION_SECRET` (at least 32 characters)
- the Staging `CORS_ORIGINS`
- `SESSION_SAMESITE=none` for the split frontend/API hosts

**Migrations are automatic in Staging.** `app/core/migrations.py::upgrade_to_head` runs in the
FastAPI lifespan on every boot (except `APP_ENV=test`), under the ChaharSooq PostgreSQL advisory
lock. The lock makes concurrent replicas single-flight; a waiting replica applies a no-op upgrade
after the first one finishes. This is still a Staging convenience, not the Production process.
Staging does not have a separate provisioning service; the managed Neon role is used as-is.

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
and Docker Compose. The production database is a PostgreSQL container on that host with its own
persistent volume. The `172.30.2.2` address is an internal address; do not assume it is publicly
reachable.

The stack is **implemented as code** in [compose.production.yml](../../compose.production.yml) and
is **not deployed**. No command in this repository connects to `market-linux`; deployment,
registry promotion, TLS, and backups remain separate work.

### Production services

| Service     | Image / build                     | Runtime identity | Exposure / purpose                                                            |
| ----------- | --------------------------------- | ---------------- | ----------------------------------------------------------------------------- |
| `db`        | `postgres:18.6-trixie`            | `999:999`        | Internal only; persistent volume at `/var/lib/postgresql`                     |
| `provision` | `Dockerfile.api` (`charsooq-api`) | `10001:10001`    | One-shot idempotent role/grant provisioning; exits 0 when the roles are ready |
| `migrate`   | `Dockerfile.api` (`charsooq-api`) | `10001:10001`    | One-shot locked migration runner; exits 0 at `head`                           |
| `api`       | `Dockerfile.api` (`charsooq-api`) | `10001:10001`    | Internal only on `backend` + `edge`; FastAPI on port `8000`                   |
| `web`       | `Dockerfile.web` (`charsooq-web`) | `1000:1000`      | Internal only on `edge`; Next.js standalone server on port `3000`             |

`db`, `provision`, `migrate`, `api`, and `web` are the only services. Redis is not part of this
stack: login rate limiting is in-memory for the current single-host deployment, and adding Redis
without a measured need would add another stateful service. The Compose project name is
`charsooq-production`, so its networks and volume are separate from the development stack.

The `api` and `migrate` services set:

```text
APP_ENV=production
DEPLOYMENT_ENV=production
RUN_MIGRATIONS_ON_STARTUP=false
RUN_OWNER_BOOTSTRAP_ON_STARTUP=false
SECRETS_DIR=/run/secrets
```

Nothing is inherited from `compose.yml` or from repo env files.

### Build and run

```bash
make prod-config    # structure only; does not read secret files
make prod-build     # build pinned API + web images
make prod-provision # run idempotent role provisioning once (needs secrets)
make prod-migrate   # run the locked migration runner once (needs secrets)
make prod-bootstrap-owner # explicit owner CLI (needs secrets)
make prod-up        # build and start the stack in dependency order
make prod-ps        # status and health
make prod-logs      # follow logs
make prod-down      # stop; volumes and data are kept
```

Equivalent direct commands:

```bash
docker compose -f compose.production.yml config
docker compose -f compose.production.yml build
docker compose -f compose.production.yml up -d --build
docker compose -f compose.production.yml ps
```

Image references are configurable with `CHARSOOQ_API_IMAGE` / `CHARSOOQ_WEB_IMAGE`. The compose file
builds from this checkout by default; a registry-based promotion should replace those references
with immutable digests (still open).

### Startup order and health

Compose enforces this order:

1. `db` starts and becomes healthy (`pg_isready` against the local socket/TCP port).
2. `provision` runs only after `db` is healthy. It creates/updates the migration and application
   roles, transfers ownership on an existing volume, applies grants/default privileges, and verifies
   the result.
3. `provision` must complete with exit code 0. A failed provision leaves it failed and `migrate` /
   `api` are never started.
4. `migrate` runs after `provision` completed successfully (and `db` is healthy). It uses only the
   migration credential.
5. `migrate` must complete with exit code 0. A failed migration, lock timeout, or bad configuration
   leaves it failed and `api` is never started.
6. `api` starts after `migrate` completed successfully and `db` is healthy. Its healthcheck calls
   `/ready`, which executes `SELECT 1` against the database as the application role.
7. `web` starts only after `api` is healthy. Its healthcheck requests `/login` from the Next server.

`provision` and `migrate` use `restart: "no"` so a one-shot failure does not loop; `db`, `api`, and
`web` use `unless-stopped`. API and web healthchecks are real requests, not process checks. The API
keeps Uvicorn at two workers (the existing single-host sizing); no worker count is raised in this
task. Provisioning and migration are serialized by their own locks, so a manual one-off cannot race
a stack start.

### Production secrets

Production uses **file-backed Docker Compose secrets**, mounted read-only at `/run/secrets`.
The host directory defaults to `/etc/charsooq/secrets` and can be overridden with
`CHARSOOQ_SECRETS_DIR`. The directory must not be inside the repository.

| Secret file              | Delivered to           | Required content                                                     |
| ------------------------ | ---------------------- | -------------------------------------------------------------------- |
| `postgres_password`      | `db`, `provision`      | Password for the administrative `charsooq` PostgreSQL role           |
| `database_url`           | `provision`, `api`     | `postgresql+psycopg://charsooq_app:<password>@db:5432/charsooq`      |
| `migration_database_url` | `provision`, `migrate` | `postgresql+psycopg://charsooq_migrator:<password>@db:5432/charsooq` |
| `session_secret`         | `api`                  | Session configuration secret, at least 32 bytes                      |
| `owner_password`         | `api`                  | Owner bootstrap password, at least 8 characters                      |
| `parsina_password`       | `api`                  | Parsina password when the integration is configured                  |

Only the services that need a secret receive it. The API never mounts `postgres_password` or
`migration_database_url`; the migration runner never mounts `postgres_password` or `database_url`.
The provisioning service receives the administrative password plus both URLs because it must create
the roles and set their passwords. The role names and passwords are taken from the URLs; both URLs
must target `db:5432/charsooq` and use different roles. `parsina_password` must exist for the stack
to start; when Parsina is intentionally disabled, an empty file keeps
`ParsinaSettings.is_configured` false.

Compose file-backed secrets are bind-mounted files. Their host ownership and mode are what the
container sees; `uid`, `gid`, and `mode` in the Compose file apply to Swarm secrets and are
deliberately not used here. Make each file unreadable by other host users and readable by the
container identity that consumes it:

```bash
# Run as root on the Production host. This changes ownership/mode only.
sudo install -d -m 0700 -o root -g root /etc/charsooq/secrets
sudo chown 999:999 /etc/charsooq/secrets/postgres_password
sudo chown 10001:10001 /etc/charsooq/secrets/database_url \
  /etc/charsooq/secrets/migration_database_url /etc/charsooq/secrets/session_secret \
  /etc/charsooq/secrets/owner_password /etc/charsooq/secrets/parsina_password
# The provision service joins GID 999 so it can read the admin password too.
sudo chmod 0440 /etc/charsooq/secrets/postgres_password
sudo chmod 0400 /etc/charsooq/secrets/database_url \
  /etc/charsooq/secrets/migration_database_url /etc/charsooq/secrets/session_secret \
  /etc/charsooq/secrets/owner_password /etc/charsooq/secrets/parsina_password
```

The file values are never printed by the API or the migration runner, and configuration errors
exclude URLs, hosts, usernames, and passwords. Secret values must not appear in Compose, Dockerfiles,
docs, logs, or images.

### Database roles and least privilege

Production now uses three roles instead of one:

| Role           | Credential                            | Rights and use                                                                                                                                                                                          |
| -------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Administrative | `POSTGRES_USER` + `postgres_password` | Superuser created by the PostgreSQL image. Used by `db` and the one-shot `provision` service only. Never delivered to `api`/`migrate`.                                                                  |
| Migration      | `migration_database_url`              | Owns schema `public` and Alembic-created objects; `CONNECT`/`CREATE` on the database; can run current and future migrations. Not a superuser and cannot create roles/databases.                         |
| Application    | `database_url`                        | `CONNECT`, schema `USAGE`, `SELECT`/`INSERT`/`UPDATE`/`DELETE` on application tables, `USAGE`/`SELECT` on sequences. No schema `CREATE`, no ownership, no role management, no `alembic_version` access. |

The committed schema lives in `public` (no migration specifies another schema). The migration role
gets ownership of that schema and of existing objects; the application role gets exact DML plus
default privileges for future tables/sequences. The implementation is
`backend/api/app/core/provisioning.py`; the service command is
`backend/api/scripts/provision_database_roles.py`.

**Why a service, not initialization scripts.** PostgreSQL `docker-entrypoint-initdb.d` scripts run
only when the data directory is empty. They cannot create roles, apply grants, or rotate passwords
on an existing `charsooq-production_pgdata` volume. The one-shot `provision` service runs on every
stack start, is idempotent, and handles both cases:

- **New volume:** `db` creates the administrative role/database, `provision` creates the migration
  and application roles, `migrate` creates the schema as the migration role, and `api` connects as
  the application role.
- **Existing single-role volume:** the old tables are owned by the administrative role. `provision`
  transfers tables/sequences/views owned by that known role to the migration role, revokes broad
  grants, applies the least-privilege set, and grants the application role. If an object is owned by
  an unexpected role, it fails closed rather than changing ownership.

**Password rotation.** Update the password inside `database_url` (application role) or
`migration_database_url` (migration role), keep the same role name and database, then run
`make prod-provision` and restart the consuming service (`api` or `migrate`). The provisioning
transaction updates the role password and converges grants; the old password stops working when the
transaction commits. Rotating the administrative password means updating `postgres_password` and
running the same provisioning step so the container and provisioning service agree; the container
also needs a restart to read the file again. Secrets are read from files, never passed as Compose
arguments, so rotation does not require editing `compose.production.yml`.

**Migrating from the previous single-URL deployment.** Take a verified backup first. Create both
role URLs with the same host/database, replace the existing `database_url` value with the
application-role URL, add `migration_database_url`, then run `make prod-provision` and
`make prod-migrate` before recreating `api`. The administrative password file does not change. The
old single-role credential is never reused as `database_url`; if both URLs name the same role,
configuration and provisioning both fail.

### Networking and exposure

```text
browser -> (future reverse proxy) -> web:3000 -> /api/* rewrite -> api:8000 -> db:5432
```

- `backend` is an internal Compose network for `db`, `provision`, `migrate`, and `api`. PostgreSQL
  is not published to the host and has no external route on that network.
- `edge` connects `api` and `web`. It also gives the API outbound access to Parsina; no internal
  Parsina network link is created in this task.
- `web` does not join `backend` and cannot reach the database directly.
- No service publishes a host port. `web:3000`, `api:8000`, and `db:5432` are reachable only inside
  the Compose project. Port publishing and TLS belong to the reverse-proxy task.
- Browser API calls stay same-origin: Next rewrites `/api/*` to `http://api:8000`. No server-only
  secret is passed to the browser bundle, and `NEXT_PUBLIC_API_URL` is not set in Production.

### Images

- `Dockerfile.api` is multi-stage. The builder installs the locked uv workspace with
  `uv sync --frozen --no-dev`; the runtime copies only the virtualenv, `app/`, `migrations/`,
  `scripts/`, and `alembic.ini`. It runs as UID/GID `10001:10001`, and app code is read-only to
  that user. Base images are pinned: `python:3.12.16-slim-bookworm` and `uv:0.12.0`.
- `Dockerfile.web` installs with `pnpm install --frozen-lockfile`, builds Next.js, and copies only
  the traced `standalone` output plus static assets and `public/`. It runs as the image's `node`
  user (UID/GID `1000:1000`). Base image: `node:22.23.5-bookworm-slim`.
- `.dockerignore` excludes `.env*`, `secrets`, local data, docs, git metadata, caches, and Compose
  files. No secret or local env file enters an image.

### Backups and recovery (next task)

Backups are **not implemented** in this task. The persistent volume is
`charsooq-production_pgdata`; `make prod-down` stops containers and keeps it, and no default target
removes volumes. The next task must define scheduled `pg_dump`/base backups, encryption, off-host
retention, and a rehearsed restore. Take a verified backup before any destructive or irreversible
migration.

### TLS and reverse proxy (out of scope)

No reverse proxy and no TLS certificate are configured, and no host port is published. The API
already sends HSTS in production application mode and the session cookie is `Secure` there, so the
browser-facing endpoint must be HTTPS when the proxy is added. Proxy choice, domain/DNS,
certificate issuance, and the decision to publish only `80`/`443` remain open. Do not expose
`db`, `api`, or `web` directly while waiting for that work.

### Remaining before a real server deployment

- Provision the six secret files on the host (`postgres_password`, `database_url`,
  `migration_database_url`, `session_secret`, `owner_password`, `parsina_password`) and verify their
  ownership/modes as the consuming UIDs; `make prod-config` only proves the compose structure.
- Choose the image registry and promotion mechanism; build once from the approved commit and deploy
  by digest. The current Compose file can build locally, but Production must not rebuild ad hoc.
- Add the reverse proxy/TLS layer and publish only its ports.
- Implement and rehearse backup/restore.
- Verify Docker Engine/Compose versions and resource limits on `market-linux`, then perform the
  controlled first deployment. No such deployment has been performed or validated in this task.

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
- `compose.yml` is a development stack even though it sets `APP_ENV: production`. It also sets
  `DEPLOYMENT_ENV=development`, so the local container stack exercises production application
  behavior without being mistaken for Production.
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
| `make prod-migrate`, `prod-bootstrap-owner` (compose services)                                             | `production`  | Allowed  |
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

The code path exists; the human release workflow does not. In particular:

- The migration **mechanism** and compose wiring exist: `scripts/migrate.py`, the advisory lock, and
  the `migrate` service in `compose.production.yml`. `make db-migrate-prod` remains the disabled
  Neon-era target and is not that step. Deploying the stack is still a manual, open decision.
- The explicit owner **command** exists and is wired as `make prod-bootstrap-owner`. Production
  still needs an approved release workflow that decides who runs it, when, and with which secret
  source.
- No data-sync command from Development or Staging into Production is approved.

Until a deployment workflow is approved, Production writes stay blocked rather than relying on an
operator to choose the right database.

## Configuration foundation (implemented)

The repository contains the configuration primitives and the Production compose definition. This
section describes implemented behavior; it does not approve a Production release or deployment.

### Settings split

- `DatabaseSettings` (`backend/api/app/core/config.py`) contains `database_url` and
  `migration_lock_timeout_seconds`. The SQLAlchemy engine and the API use
  `get_database_settings()`; they never see the migration credential or the administrative
  password. Database configuration therefore works without authentication secrets.
- `MigrationSettings` contains `migration_database_url` (plus a `database_url` compatibility
  fallback and the lock timeout). `app/core/migrations.py` and `migrations/env.py` use
  `get_migration_settings()`. Production requires the dedicated URL and refuses the application
  role; Development/Staging fall back when it is unset.
- `ProvisioningSettings` contains both URLs plus `postgres_password` and `postgres_user`. It is
  instantiated only by the one-shot `provision` service, so the API and migration runner can never
  read the administrative password.
- `Settings` inherits `DatabaseSettings` and adds application behavior: `APP_ENV`, session, owner,
  CORS, sync, `RUN_MIGRATIONS_ON_STARTUP`, and `RUN_OWNER_BOOTSTRAP_ON_STARTUP`. Its public fields
  and consumers are unchanged apart from the new startup switch.
- `ParsinaSettings` remains separate and optional. Its password can come from the environment or a
  secret file and it is not required to boot the API.

### Secret files (`SECRETS_DIR`)

When `SECRETS_DIR` is set, settings read one value per file from that directory. Expected file
names:

| Secret file              | Setting / reader                     | Required in Production?                                                     |
| ------------------------ | ------------------------------------ | --------------------------------------------------------------------------- |
| `database_url`           | `DATABASE_URL` (API/provision)       | Yes, application role, PostgreSQL, non-loopback.                            |
| `migration_database_url` | `MIGRATION_DATABASE_URL` (migrate)   | Yes, migration role, PostgreSQL, non-loopback, different role from the API. |
| `postgres_password`      | `POSTGRES_PASSWORD` (provision only) | Yes for provisioning; never read by `DatabaseSettings`/`MigrationSettings`. |
| `session_secret`         | `SESSION_SECRET`                     | Yes (existing production rule).                                             |
| `owner_password`         | `OWNER_PASSWORD`                     | Yes (existing production rule, minimum 8 chars).                            |
| `parsina_password`       | `PARSINA_PASSWORD`                   | No for settings; the Production Compose file still expects the file.        |

Precedence, highest first:

1. constructor arguments,
2. environment variables,
3. env files (`backend/api/.env.local`, `backend/api/.env`, ...),
4. files under `SECRETS_DIR`.

Environment variables therefore keep their documented precedence. Secret values are not logged or
included in configuration errors. An explicitly set `SECRETS_DIR` must be an existing directory in
every environment; a missing directory fails fast. Production sets it to `/run/secrets`, where
Compose mounts the file-backed secrets described above. `postgres_password` is consumed by the
PostgreSQL image and by `ProvisioningSettings` only; it is not read by `Settings`,
`DatabaseSettings`, or `MigrationSettings`.

When `DEPLOYMENT_ENV=production` is explicit, configuration fails closed if:

- `DATABASE_URL` is missing, resolves to the committed localhost development default, is not a
  PostgreSQL URL, has no explicit host, or targets `localhost`, `127.0.0.0/8`, `::1`, or an
  IPv4-mapped loopback address;
- `MIGRATION_DATABASE_URL` is missing, resolves to the localhost default, is not PostgreSQL, has no
  explicit host, targets a loopback address, or uses the same role as `DATABASE_URL` — including
  when Alembic runs in offline SQL mode;
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

Production starts the API only after role provisioning, `scripts/migrate.py`, and, when needed,
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
| Reverse proxy           | Which proxy (Caddy, Nginx, Traefik, …), and who terminates TLS?                                                             |
| DNS / TLS               | Production domain(s), DNS ownership, certificate issuance and renewal.                                                      |
| Secrets operations      | Who provisions and rotates the host secret files, and how are permissions audited?                                          |
| Registry                | Which container registry, image retention, and access control?                                                              |
| Artifact promotion      | Can Staging and Production share one artifact, or only a commit SHA mapping?                                                |
| Deploy access           | Self-hosted runner or SSH from CI? Which account and approvals?                                                             |
| Migration control       | Who approves and triggers the Production compose release, and what backup gate applies before destructive migrations?       |
| Role password rotation  | Who rotates the application, migration, and administrative passwords, on what schedule, and how the backup gate applies.    |
| Backup / DR             | Tooling, schedule, retention, off-site storage, RPO/RTO, restore drills.                                                    |
| Observability           | Logs, metrics, uptime checks, alerting, and error tracking for each environment.                                            |
| Staging identity        | Staging frontend/API domains, Vercel environment scope, and whether Staging tracks `main` or an explicit release candidate. |
| Data policy             | Exact approval and sanitization process for any real data used outside Production.                                          |
| Production data seeding | How the owner account and initial catalog are provisioned without sharing secrets.                                          |

See also [overview.md](overview.md), [backend.md](backend.md), [database.md](database.md), and
[ADR 011](../adr/011-three-environment-architecture.md).
