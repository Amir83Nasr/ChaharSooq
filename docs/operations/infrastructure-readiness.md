# Infrastructure readiness and pre-deployment audit — چهارسوق

Status: **audit only**. Nothing in this document was executed against `market-linux`. The server was
not contacted, no SSH session or remote command was run, no port was scanned, no Production Compose
stack was started, no database was opened, and no `.env` or secret file was read. Every statement
below is backed by a file in this repository or by an explicitly unanswered IT question.

Related: [Production runbook](production-runbook.md) · [Troubleshooting](troubleshooting.md) ·
[Backup and recovery](backup-and-recovery.md) ·
[TLS certificate lifecycle](tls-certificate-lifecycle.md) ·
[IT requirements checklist](it-requirements.md) ·
[Deployment](../architecture/deployment.md) ·
[ADR 012](../adr/012-internal-reverse-proxy-and-tls.md) ·
[ADR 013](../adr/013-tls-certificate-lifecycle.md) ·
[ADR 014](../adr/014-production-backup-and-recovery.md)

## 1. How to read this document

| Status  | Meaning                                                                                              |
| ------- | ---------------------------------------------------------------------------------------------------- |
| Ready   | Implemented, committed, and verified as far as the repository can verify it.                         |
| Partial | Implemented, but it needs completion, an approval, or an operational decision before it can be used. |
| Blocked | The code exists; a value or capability from the organization's environment is required to use it.    |
| Missing | Not implemented. Nothing in the repository provides it.                                              |

A **Blocked** item is not a defect. The Production stack is deliberately built to fail closed when
an IT-owned value is missing: `compose.production.yml` requires four deployment values with no
defaults (`:?` interpolation), so an unconfigured stack refuses to start instead of publishing a
port on every interface or trusting an unverified proxy.

Two different questions are kept apart throughout this document:

- **Can the stack start?** — the technical answer, decided by code plus a handful of IT values.
- **Can users use the panel?** — the operational answer, which additionally needs network access,
  certificate trust on client machines, monitoring, and a verified backup.

The questions to IT, with the stage each answer is needed for, are in
[it-requirements.md](it-requirements.md).

## 2. Repository readiness

### 2.1 Summary

| #   | Item                                         | Status  | One-line reason                                                                   |
| --- | -------------------------------------------- | ------- | --------------------------------------------------------------------------------- |
| 1   | Production Docker Compose                    | Ready   | Six services, ordered, structurally validated; never started on a host            |
| 2   | API and web Dockerfiles                      | Ready   | Multi-stage, pinned bases, non-root, healthchecks                                 |
| 3   | Caddy and reverse proxy                      | Ready   | Pinned image, one upstream, isolated network, hardened                            |
| 4   | TLS and certificate lifecycle                | Partial | Lifecycle tooling complete; renewal policy and real material are open             |
| 5   | PostgreSQL and role provisioning             | Ready   | Three least-privilege roles, idempotent one-shot provisioner                      |
| 6   | Alembic and migration runner                 | Ready   | Locked one-shot runner; CI proves idempotency, single head, and round-trip        |
| 7   | Owner bootstrap                              | Partial | Command exists and is idempotent; the release workflow that authorises it is open |
| 8   | Secret file management                       | Partial | File-backed mechanism and least privilege ready; custodian and schedule are open  |
| 9   | Backup and restore                           | Partial | Designed and rehearsed offline; no scheduler, destination, or alerting exists     |
| 10  | Healthcheck and readiness                    | Ready   | Real readiness checks per service, enforced by `depends_on`                       |
| 11  | Logging and log rotation                     | Partial | Per-container rotation is enforced; host rotation and collection are IT decisions |
| 12  | Makefile and operational commands            | Ready   | Complete production target set; no target removes a volume                        |
| 13  | CI/CD and image publishing                   | Partial | Publishing workflow exists and is untested; no deploy workflow                    |
| 14  | Deployment and troubleshooting documentation | Ready   | Architecture, runbook, troubleshooting, backup, TLS, and ADR set                  |

### 2.2 Evidence per item

**1 — Production Docker Compose: Ready.**
[`compose.production.yml`](../../compose.production.yml) defines exactly six services — `db`,
`provision`, `migrate`, `api`, `web`, `caddy` — with project name `charsooq-production`, so its
networks and volumes are separate from the development stack. The start order is encoded, not
conventional: `provision` waits for `db` to be `service_healthy`, `migrate` waits for
`service_completed_successfully`, and `api` is not created until the migration succeeded. Four
deployment values have no defaults (`CHARSOOQ_PROXY_BIND_IP`, `CHARSOOQ_SITE_HOST`,
`CHARSOOQ_EDGE_SUBNET`, `CHARSOOQ_WEB_EDGE_IP`). `make prod-config` passes locally: it
interpolates RFC 5737 documentation addresses and proves the file is well formed, nothing more.
The stack has never been started on a host, so the first real container start remains a validation
step.

**2 — API and web Dockerfiles: Ready.**
[`Dockerfile.api`](../../Dockerfile.api) is multi-stage: the builder installs the locked workspace
with `uv sync --frozen --no-dev`, and the runtime image carries only the virtualenv, `app/`,
`migrations/`, `scripts/`, and `alembic.ini`. It runs as UID/GID `10001:10001` with the code
read-only to that user, and declares its own `HEALTHCHECK` against `/ready`. Base images are pinned
(`python:3.12.16-slim-bookworm`, `uv:0.12.0`). [`Dockerfile.web`](../../Dockerfile.web) installs
with `pnpm install --frozen-lockfile`, builds Next.js, and copies only the traced `standalone`
output plus static assets; it runs as the image's `node` user and has a `HEALTHCHECK` against
`/login`. `.dockerignore` excludes `.env*`, `**/secrets`, `deploy`, and certificate extensions, so
no secret or TLS material can enter an image.

**3 — Caddy and reverse proxy: Ready.**
Configuration lives in [`deploy/caddy/`](../../deploy/caddy/): `Caddyfile`, `site.caddy`,
`tls-organization.caddy`, `tls-internal-ca.caddy`. The container runs the pinned
`caddy:2.11.9-alpine` with `read_only: true`, `cap_drop: [ALL]`, `cap_add: [NET_BIND_SERVICE]`,
`security_opt: [no-new-privileges:true]`, `admin off`, and `skip_install_trust`. It joins the
`proxy` network only, so it has no route to `api`, `db`, `provision`, or `migrate`; `web` is the
single upstream. `site.caddy` owns HSTS and strips client-supplied `X-Forwarded-*`, `Forwarded`,
and `X-Real-IP`. The global block restricts listeners to `h1 h2`, so Caddy never advertises an
`alt-svc` HTTP/3 endpoint that Compose does not publish. The configuration was adapted and validated
offline with the official 2.11.9 binary; the container itself has not been started.

**4 — TLS and certificate lifecycle: Partial.**
The tooling is complete: [`deploy/tls/validate_certificate.py`](../../deploy/tls/validate_certificate.py)
checks PEM structure, key match, chain order, trust anchor, expiry, SAN match, and key permissions
offline and prints no key material; [`deploy/tls/activate_certificate.py`](../../deploy/tls/activate_certificate.py)
stages a pair under `versions/<stamp>/` and switches the single `current` symlink with one atomic
`os.replace`, so Caddy can never start from a mismatched pair. `make tls-validate`,
`make tls-activate`, `make tls-rollback`, and `make prod-caddy-validate` expose the gates.
What is missing is operational, not technical: renewal is manual with no CA automation, the renewal
policy and its owner are open IT decisions, and no real certificate, DNS name, or approved IP
exists. See [ADR 013](../adr/013-tls-certificate-lifecycle.md).

**5 — PostgreSQL and role provisioning: Ready.**
Production separates three roles: the image-created administrative superuser (used only by `db` and
the one-shot `provision` service), a migration role that owns schema `public`, and an application
role with `CONNECT`, schema `USAGE`, and exact DML on application tables. The implementation is
[`backend/api/app/core/provisioning.py`](../../backend/api/app/core/provisioning.py) and the
service command is
[`backend/api/scripts/provision_database_roles.py`](../../backend/api/scripts/provision_database_roles.py).
It is idempotent on a fresh volume and on an existing single-role volume, where it transfers
ownership, revokes broad grants, applies the least-privilege set, and grants default privileges
for future tables. It fails closed when an object is owned by an unexpected role.

**6 — Alembic and migration runner: Ready.**
[`backend/api/scripts/migrate.py`](../../backend/api/scripts/migrate.py) applies `head` under a
PostgreSQL session-level advisory lock
([`backend/api/app/core/migration_lock.py`](../../backend/api/app/core/migration_lock.py)); it never
calls `create_all`, never prints a URL, and exits non-zero on failure or lock timeout. The Compose
`migrate` service receives only the migration credential and gates `api` on
`service_completed_successfully`. CI proves a fresh upgrade, an idempotent re-upgrade, a single
head, `alembic check` drift detection, and a full downgrade/upgrade round-trip.

**7 — Owner bootstrap: Partial.**
[`backend/api/scripts/bootstrap_owner.py`](../../backend/api/scripts/bootstrap_owner.py) and
`make prod-bootstrap-owner` exist, are idempotent, never call `create_all`, refuse when the
`admins` table is missing, and preserve the single-owner invariant. Production runs with
`RUN_OWNER_BOOTSTRAP_ON_STARTUP=false`, so this is the explicit step. What is missing is the
release workflow: who runs it, in which window, and from which secret source is still an open
decision, and Production owner provisioning is listed as unresolved in
[deployment.md](../architecture/deployment.md#approved-production-paths).

**8 — Secret file management: Partial.**
The mechanism is ready: file-backed Compose secrets mounted read-only at `/run/secrets`, one file
per value, and only the services that need a secret receive it. The API never mounts
`postgres_password` or `migration_database_url`; the migration runner never mounts the
administrative password or the application URL. `SECRETS_DIR` precedence, the six expected file
names, and the required host ownership and mode are documented and enforced by configuration
checks. What is missing is custody: who provisions the files, how permissions are audited, how
often they are rotated, and where the values are recovered from are open decisions — the backup
runbook explicitly excludes secret files from the database backup.

**9 — Backup and restore: Partial.**
The design is complete and was rehearsed offline against a throwaway PostgreSQL 18.6 cluster with
synthetic data: an encrypted `pg_dump` custom-format archive, verified by listing or a scratch
restore, restored **before** `provision` so ownership converges afterwards. The gate before a
destructive migration is defined. What does not exist: a scheduler, an off-host destination, an
approved encryption tool and key custodian, an enforced retention policy, backup alerting, a
dedicated backup role, and PITR/WAL archiving. The recovery point is the last verified dump, not
the last transaction. See [ADR 014](../adr/014-production-backup-and-recovery.md).

**10 — Healthcheck and readiness: Ready.**
`db` runs `pg_isready` against the local socket; `api` runs a real request to `/ready`, which
executes `SELECT 1` as the application role; `web` requests `/login` from the Next server and fails
only on a server error. Compose enforces the order through `depends_on` conditions, and
`docker compose ps` reports `healthy`/`unhealthy`/`starting`. The API also exposes `/health` and
`/ready` for external probes. Caddy has no container healthcheck by design: it is verified from
outside over HTTPS.

**11 — Logging and log rotation: Partial.**
Every service is bounded by the Compose `json-file` driver with `max-size: 10m` and `max-file: 5`,
and a test fails the build if any service drifts from that. Caddy writes a JSON access log to
stdout without credentials (`log_credentials` is never enabled; a static test guards it), and the
API does not log bodies, passwords, session IDs, or database URLs. Missing: host-level log
retention, central collection, and an archival period — all recorded as IT decisions. Containers
created before this setting must be recreated once to adopt it.

**12 — Makefile and operational commands: Ready.**
The production target set is complete: `prod-config`, `prod-build`, `prod-provision`,
`prod-migrate`, `prod-bootstrap-owner`, `prod-up`, `prod-ps`, `prod-logs`, `prod-down`,
`prod-caddy-validate`, `tls-validate`, `tls-activate`, `tls-rollback`. `make help` lists every
target with a description. No target runs `docker compose down -v`, prunes volumes, or removes
`pgdata`; the legacy Neon-era production targets are disabled and fail closed with a reason.

**13 — CI/CD and image publishing: Partial.**
[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) runs `frontend`, `backend`,
`migrations`, and `build` jobs — lint, format, typecheck, both test suites, the migration
idempotency/drift/round-trip checks, the OpenAPI freshness check, the production build, and the
Playwright e2e suite. It is now also **reusable** (`workflow_call`), so the release workflow can run
the same checks against the exact release commit.

[`.github/workflows/release.yml`](../../.github/workflows/release.yml) publishes `charsooq-api` and
`charsooq-web` from a published GitHub Release: it checks out the release tag, verifies the commit,
runs the checks, builds both images from that one checkout, tags them with the version and the commit
SHA, attaches provenance and an SBOM, verifies the published `revision` label against the release
commit, and records both digests in the release body. It uses `GITHUB_TOKEN` only, so no new secret
is needed. The decision is [ADR 015](../adr/015-container-image-release-and-publishing.md) and the
procedure is [release-management.md](release-management.md).

What is still missing: the workflow has **never been executed** — no release exists, no registry
package has been created, and the registry itself is an open IT decision (question 4.6). There is
still **no deploy workflow**: publishing an image does not deploy it, and the promotion from Staging
to Production stays a manual, explicit step.

**14 — Deployment and troubleshooting documentation: Ready.**
Architecture and environment boundaries: [`docs/architecture/deployment.md`](../architecture/deployment.md).
Procedures: [`production-runbook.md`](production-runbook.md),
[`troubleshooting.md`](troubleshooting.md), [`backup-and-recovery.md`](backup-and-recovery.md),
[`tls-certificate-lifecycle.md`](tls-certificate-lifecycle.md). Decisions: ADR 011 (environments),
ADR 012 (reverse proxy and TLS), ADR 013 (TLS lifecycle), ADR 014 (backup and recovery). The
runbook's preflight, first-start sequence, incident matrix, and the troubleshooting failure matrix
are command-level and executable as written.

### 2.3 What "Ready" does not mean here

Every Ready item above is verified **as code in this repository**. None of them has been exercised
on `market-linux`. The first real container start, the first real `caddy validate` against real
certificate material, and the first real end-to-end login are validation steps of the first
deployment, not evidence gathered before it.

## 3. Server prerequisites

All of the following are **Blocked**: the answers belong to the organization's environment, and
the repository must not guess them. The values are also collected as questions in
[it-requirements.md](it-requirements.md).

### 3.1 Operating system and resources

| Requirement           | Needed value                                                           | Why it matters                                                                         | Status  |
| --------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------- |
| Linux distribution    | Ubuntu, with the exact release confirmed by IT                         | The stack targets a Docker Engine host; the base images are Debian-family              | Blocked |
| Kernel / architecture | `x86_64` or `arm64`, confirmed                                         | Base image multi-arch availability and any host-specific tooling                       | Blocked |
| CPU                   | Minimum 2 vCPU, 4 vCPU recommended                                     | Compose limits each service to 1 CPU; `db`, `api`, `web`, and `caddy` run at once      | Blocked |
| RAM                   | Minimum 4 GiB, 8 GiB recommended                                       | Compose limits total 2.75 GiB if every service ran simultaneously, plus host overhead  | Blocked |
| Disk                  | Minimum 40 GiB free on the Docker filesystem, 60 GiB recommended       | Images, layers, the PostgreSQL volume, and a logical dump plus encryption overhead     | Blocked |
| Separate storage      | A second location or allocatable space for database and backup volumes | A copy on the same host is not an off-host backup                                      | Blocked |
| NTP / clock sync      | `timedatectl show -p NTPSynchronized` must report `yes`                | Certificate validity checks, session expiry, and log correlation fail on a wrong clock | Blocked |

The Compose `deploy.resources.limits` are ceilings, not a capacity plan: `provision` and `migrate`
are sequential one-shots, so the realistic peak is `db` + `api` + `web` + `caddy`, plus the host,
the Docker daemon, and PostgreSQL shared buffers.

### 3.2 Docker

| Requirement        | Needed value                                                                           | Why it matters                                                     | Status  |
| ------------------ | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------- |
| Docker Engine      | A supported Engine release approved by IT                                              | The stack uses Compose features that older Engines do not support  | Blocked |
| Docker Compose     | Compose v2 with `depends_on.condition`, `name:`, and `--wait` support                  | `service_completed_successfully` and `up --wait` are required      | Blocked |
| Daemon             | Running and reachable by the deploy account                                            | `docker info` must succeed for the operator                        | Blocked |
| Deploy user access | The named deployment account in the `docker` group                                     | The group is root-equivalent; membership must be named and audited | Blocked |
| Restart policy     | Daemon-level restart on boot; Compose already sets `unless-stopped` per service        | A host reboot must bring the panel back without manual action      | Blocked |
| Registry / pull    | Whether images are pulled from a registry or built on the host; proxy and mirror rules | An air-gapped or proxied environment changes the release path      | Blocked |

The Compose file itself already provides the per-service restart policy: `unless-stopped` for `db`,
`api`, `web`, and `caddy`, and `restart: "no"` for the two one-shot services so a failure does
not loop.

### 3.3 Network

| Requirement              | Needed value                                                      | Why it matters                                                                      | Status  |
| ------------------------ | ----------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------- |
| Fixed internal IP        | The approved address Caddy binds `80`/`443` to                    | `CHARSOOQ_PROXY_BIND_IP`; a bare `80:80` would publish on every interface           | Blocked |
| Internal DNS name        | The name users open, matching the certificate SAN exactly         | `CHARSOOQ_SITE_HOST`; the browser URL must equal the SAN                            | Blocked |
| User reachability        | The network segment or VLAN the organization grants access from   | Decides who can open the panel                                                      | Blocked |
| TCP 80 and 443           | Confirmation that both are free and inbound is permitted          | The redirect and TLS termination both depend on them                                | Blocked |
| IPv4 / IPv6 status       | Whether the host and LAN use IPv6, and whether the panel needs it | No IPv6 binding is configured; enabling it needs firewall and certificate decisions | Blocked |
| Firewall and VLAN policy | The rules that permit inbound `443` from the client segment       | Reachability, and whether anything besides `443` should be permitted                | Blocked |
| Docker subnet conflicts  | The Docker address pools and the organization's routes            | `CHARSOOQ_EDGE_SUBNET` must not overlap a LAN, VPN, or Docker pool                  | Blocked |

The `proxy` network deliberately carries **no** subnet, so Docker assigns it from its own pool;
a later collision is resolved with an approved `ipam` block or the daemon's
`default-address-pools`, not by editing the Compose file. The `edge` network does require an
explicit CIDR because `web` needs a fixed address there — Uvicorn matches its trusted proxy by IP
only.

## 4. TLS and internal access

The architecture is decided in [ADR 012](../adr/012-internal-reverse-proxy-and-tls.md); the
lifecycle is in [ADR 013](../adr/013-tls-certificate-lifecycle.md) and
[tls-certificate-lifecycle.md](tls-certificate-lifecycle.md). What is missing is never a code
change — it is an organizational answer.

| Item                                           | Status  | Evidence / dependency                                                                                                                 |
| ---------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Internal DNS                                   | Blocked | Must exist before a DNS SAN is chosen; `getent ahosts` from a client must resolve                                                     |
| Proposed ChaharSooq domain                     | Blocked | The name must be approved and must equal the certificate SAN; no placeholder name is committed here                                   |
| Organization certificate authority             | Blocked | Selects `CHARSOOQ_TLS_MODE=organization` versus `internal-ca`; the organization CA is the priority                                    |
| Issuance with a DNS SAN or an IP SAN           | Blocked | Both shapes are supported by the committed snippets; a DNS SAN is preferred                                                           |
| Root CA distribution to organization computers | Blocked | Required for `internal-ca`; Group Policy or an equivalent client-management tool must be available                                    |
| Group Policy / client management tooling       | Blocked | Decides whether `internal-ca` is usable at all, and how the root is installed                                                         |
| Certificate renewal policy                     | Blocked | Manual with a 30-day lead today; the owner and the calendar entry are not assigned                                                    |
| Custodian of the private key                   | Blocked | The host key is `0600` and read only by Caddy; the organizational custodian is not named                                              |
| Backup and recovery of Caddy information       | Partial | Designed and rehearsed offline for `caddy_data`/`caddy_config` and the certificate directory; no scheduler or destination is approved |

Decisions that cannot be closed without an IT answer:

1. Whether an internal DNS service exists, and the final name.
2. Whether the organization runs a certificate authority, and whether it issues DNS SANs, IP SANs,
   or both.
3. Whether the CA or root certificate can be pushed to clients by Group Policy or an equivalent
   tool.
4. The issuer, SAN type, validity period, and renewal policy for the certificate.
5. The approved fixed internal IP, and therefore the bind address and the `edge` subnet.

## 5. Backup and recovery

Nothing in the table below is marked Ready that is not implemented. The authoritative detail is
[backup-and-recovery.md](backup-and-recovery.md); the decision is
[ADR 014](../adr/014-production-backup-and-recovery.md).

| Item                            | Status  | Evidence                                                                                                                    |
| ------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------- |
| Scheduled backup run            | Missing | No timer, cron entry, agent, or systemd unit is committed; the dump is a documented manual procedure                        |
| Destination off the server      | Blocked | The procedure names an approved off-host destination, but it is not defined, and the transport is undecided                 |
| Backup encryption               | Partial | The format is defined (encrypted archive, `openssl enc` explicitly rejected); the approved tool is not chosen               |
| Encryption key custody          | Blocked | The key must be held separately from the archive; no custodian, storage location, or rotation is assigned                   |
| Retention policy                | Partial | A daily/weekly/monthly proposal is documented but not configured, and legal hold is undefined                               |
| Periodic restore test           | Partial | Required before go-live and on an agreed cadence; the procedure is documented but has not been performed against Production |
| PITR and WAL archiving          | Missing | No `archive_mode`, no `archive_command`, no base backup, no `restore_command`; explicitly out of scope in ADR 014           |
| RPO and RTO                     | Blocked | Open decision; it determines the dump frequency and whether PITR is required                                                |
| Who confirms a backup succeeded | Blocked | The manual checklist exists, but no owner is named and no scheduler exists to enforce it                                    |
| Alert on backup failure         | Missing | No alert channel exists; a missed backup is silent until the checklist is run manually                                      |

The one implemented and rehearsed capability is the baseline itself: an encrypted logical dump,
restored before `provision` so ownership converges, verified in a scratch container, with a backup
gate before destructive migrations.

## 6. Image and release management

| Item                                           | Status  | Evidence / gap                                                                                                                                                |
| ---------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Build the image                                | Ready   | `make prod-build` builds `Dockerfile.api` and `Dockerfile.web` from the current checkout, tagged by commit and stamped with the commit SHA                    |
| Publish to GitHub Container Registry           | Partial | The release workflow exists and is reviewed, but it has never run: no release, no registry package, and the registry is an open IT decision                   |
| Tag and versioning                             | Ready   | Two immutable tags per image — the release version and `sha-<full-sha>`; the workflow refuses to publish a version tag twice, and `latest` is never used      |
| Use an immutable digest                        | Ready   | The workflow records both digests in the release body, the run summary, and an artifact; `CHARSOOQ_API_IMAGE` / `CHARSOOQ_WEB_IMAGE` take `repo@sha256:…`     |
| Detect a stale image                           | Ready   | Both images carry `org.opencontainers.image.revision`; the workflow reads it back from the registry, and `make prod-image-revision` checks the deployed image |
| Provenance and SBOM                            | Ready   | BuildKit provenance and SBOM attestations travel inside the published image index, plus a GitHub build provenance attestation for each digest                 |
| Promote Staging to Production                  | Blocked | Staging runs on Vercel/FastAPI Cloud and Production on Docker; a shared artifact is not proven, and the mapping is a documented decision                      |
| Run the migration before updating the API      | Ready   | `make prod-migrate` runs first; `api` depends on `service_completed_successfully`, so a failed migration stops the release                                    |
| Rollback plan                                  | Ready   | Code-only rollback by previous digest is documented; an incompatible migration requires a restore, not `alembic downgrade`                                    |
| Migration compatible with the previous version | Partial | The expand/contract rule is documented, but each migration still needs an explicit classification at release time                                             |

### 6.1 The baseline for the first deployment

The release identity is the **Git commit SHA**, as
[deployment.md](../architecture/deployment.md#artifacts-and-version-traceability) already requires.
For the first deployment the approved baseline is:

- the commit SHA that the organization approves, which must be a commit whose CI jobs `frontend`,
  `backend`, `migrations`, and `build` are green, and which has been exercised in Staging;
- the images built from that exact commit — published by the release workflow, selected by digest,
  or, until a registry exists, a host build from a clean checkout of that commit, with the image IDs
  recorded;
- the database revision that ships with it, recorded from `alembic_version` before and after the
  release.

Concretely, for the first deployment the baseline is the **tip commit of `main` at the moment of
approval**, published as one release, with the SHA and both digests recorded in the release body.
At the time of this audit the `main` tip was `dadb614` ("docs(ops): add infrastructure readiness
audit and IT requirements checklist"), which sits on top of the TLS-lifecycle, reverse-proxy, and
backup work; re-read the tip at approval time rather than relying on that value. Two conditions
attach: the working tree on the deployment host must be clean at the approved SHA
(`git status --porcelain` empty, `git describe` not `-dirty`), and the image must be pulled from the
published digest rather than taken from a stale local cache. If the organization approves a
different SHA, that SHA is the baseline instead — the point is that the SHA is explicit, not
implied.

## 7. Deployment readiness matrix

| Subject                                    | Status  | Prerequisite                                                                                                                                                  | Who provides          | Blocks the first deployment?                     |
| ------------------------------------------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- | ------------------------------------------------ |
| Production Compose stack                   | Ready   | Docker Engine + Compose v2 on the host                                                                                                                        | IT                    | No — the code is ready                           |
| API and web images                         | Ready   | A builder with the toolchain, or a registry                                                                                                                   | Team / IT             | No                                               |
| Approved internal IP                       | Blocked | `CHARSOOQ_PROXY_BIND_IP`                                                                                                                                      | IT                    | **Yes**                                          |
| Internal DNS name                          | Blocked | `CHARSOOQ_SITE_HOST`, equal to the certificate SAN                                                                                                            | IT                    | **Yes**                                          |
| `edge` subnet and fixed web address        | Blocked | `CHARSOOQ_EDGE_SUBNET`, `CHARSOOQ_WEB_EDGE_IP`, conflict-checked                                                                                              | IT                    | **Yes**                                          |
| TLS material or CA decision                | Blocked | `CHARSOOQ_TLS_MODE` plus a validated certificate pair, or an `internal-ca` decision                                                                           | IT                    | **Yes**                                          |
| Six secret files on the host               | Partial | `postgres_password`, `database_url`, `migration_database_url`, `session_secret`, `owner_password`, `parsina_password`, with the documented ownership and mode | IT / secret custodian | **Yes**                                          |
| Docker daemon and deploy account access    | Blocked | Docker running; the deploy account in the `docker` group                                                                                                      | IT                    | **Yes**                                          |
| Deployment checkout at the approved commit | Ready   | A clean checkout at the approved SHA, plus the four exported deployment values                                                                                | Team                  | **Yes** — the values have no defaults            |
| Port availability on 80/443                | Blocked | Confirmation that both ports are free and inbound is permitted                                                                                                | IT                    | **Yes**                                          |
| Database role provisioning                 | Ready   | The admin password and both role URLs                                                                                                                         | Team                  | No                                               |
| Schema migration                           | Ready   | The migration credential                                                                                                                                      | Team                  | No                                               |
| Owner bootstrap                            | Partial | `owner_password`, and an approved release workflow that says who runs it                                                                                      | Team + owner          | No — it is a separate explicit step              |
| Backup before the first migration          | Partial | A verified encrypted dump — not needed on a fresh volume, mandatory before migrating existing data                                                            | Team                  | No for a fresh volume; **yes** for existing data |
| Backup tooling, destination, key custody   | Blocked | An approved tool, an off-host destination, and a key custodian                                                                                                | IT                    | No for start; **yes** before go-live             |
| Restore drill                              | Partial | A scratch-container restore of a real archive, recorded                                                                                                       | Team                  | No for start; **yes** before go-live             |
| Backup scheduler and alerting              | Missing | A timer and an alert channel                                                                                                                                  | IT                    | No                                               |
| PITR and WAL archiving                     | Missing | A separate ADR plus storage, tooling, and a drill                                                                                                             | Team + IT             | No                                               |
| Container health and readiness             | Ready   | None beyond the stack                                                                                                                                         | Team                  | No                                               |
| Log rotation on the host                   | Partial | Host-level logrotate or a log collector                                                                                                                       | IT                    | No                                               |
| Registry and image publishing              | Partial | A registry IT accepts, credentials if it is not GitHub Container Registry, retention rules, and pull access from the Production host                          | IT                    | No — a host build is the recorded fallback       |
| CI deploy workflow                         | Missing | Self-hosted runner or an approved SSH deployment path                                                                                                         | IT                    | No                                               |
| Image `revision` label                     | Ready   | None — both images carry the commit SHA and the release workflow verifies it against the published bytes                                                      | Team                  | No                                               |
| Firewall / VLAN for client access          | Blocked | Inbound `443` from the approved client segment                                                                                                                | IT                    | **Yes** for user access                          |
| Root CA distribution to clients            | Blocked | Group Policy or an equivalent mechanism, in `internal-ca` mode                                                                                                | IT                    | **Yes** for user access in `internal-ca`         |
| Monitoring and alert channel               | Blocked | A paging channel and an owner                                                                                                                                 | IT                    | No for start; **yes** for go-live                |
| Certificate renewal ownership              | Blocked | A named owner and a calendar entry                                                                                                                            | IT                    | No for start; **yes** for go-live                |

### 7.1 Blocking the first deployment

These must all be answered before the stack can be started at all. Each one is an input the code
requires and refuses to guess:

1. `CHARSOOQ_PROXY_BIND_IP` — the approved internal IP.
2. `CHARSOOQ_SITE_HOST` — the approved DNS name or IP, equal to the certificate SAN.
3. `CHARSOOQ_EDGE_SUBNET` — a conflict-free CIDR for the `web` ↔ `api` network.
4. `CHARSOOQ_WEB_EDGE_IP` — `web`'s fixed address inside that CIDR.
5. The TLS decision and material — either a validated organization certificate pair, or an explicit
   `internal-ca` decision plus a plan to distribute the root.
6. The six secret files on the host, with the ownership and mode their consuming UIDs require.
7. A running Docker daemon with Compose v2, and a deploy account that can use it.
8. A deployment checkout at the approved commit, with the images already built from it.

### 7.2 Blocking user access (not the first start)

These do not stop the stack from starting, but the panel must not be opened to users until they are
answered:

1. Firewall/VLAN approval so the client segment can reach `443`.
2. DNS resolution working on client machines, or a decision to use the IP directly.
3. Root CA trust on the client machines — in `internal-ca` mode, every browser that must trust the
   site.
4. A verified backup, a rehearsed restore, and an agreed RPO/RTO.
5. A monitoring channel and a named owner for certificate-expiry and backup-failure alerts.
6. A named certificate-renewal owner and a calendar entry.

### 7.3 Can be completed later

These are real gaps, but none of them prevents the first deployment or the first user access:
a registry and image publishing pipeline, a CI deploy workflow, an OCI `revision` label, host-level
log rotation and central collection, a backup scheduler and alerting, a dedicated backup role,
PITR/WAL archiving, non-root Caddy, IPv6, HTTP/3, and high availability.

## 8. Work that can continue without IT

These do not depend on an organizational answer:

- Build and unit-test the application changes; run `make check`.
- Extend the Compose and proxy test suite; the structure is asserted by
  `backend/api/tests/test_production_compose.py` and `backend/api/tests/test_production_proxy.py`.
- Improve the offline TLS tooling and rehearse rotation and rollback with throwaway material.
- Rehearse the backup and restore procedure against a scratch PostgreSQL container with synthetic
  data, as ADR 014 already does.
- Rehearse the release workflow end to end once IT accepts a registry: publish a test release,
  pull it on a non-Production host, and verify the digests, the `revision` label, the provenance, and
  the SBOM.
- Draft the client-facing and operator-facing documentation for the panel.

## 9. Work that must wait for IT

These stop at the question in [it-requirements.md](it-requirements.md):

- Choosing the bind address, DNS name, and `edge` subnet.
- Choosing the TLS shape and obtaining the certificate material.
- Writing the six secret files to the host.
- Standing up the host: Docker Engine, Compose v2, the deploy account, the checkout path, the
  `/etc/charsooq` directories.
- Opening ports 80/443 and the firewall/VLAN rules.
- Publishing or pulling images from a registry.
- Standing up the backup destination, the encryption key custody, and the retention job.
- Standing up monitoring, alerting, and the on-call ownership.
- Naming the certificate-renewal owner and the release approver.

## 10. Verification performed for this audit

Every check below was offline and read-only, except the local image build, which ran on the
developer's machine and produced no Production artifact.

| Check                                                                                                                                                                                              | Result                                                                                         |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `make prod-config`                                                                                                                                                                                 | Pass — structure valid with RFC 5737 documentation values only                                 |
| `make prod-build`                                                                                                                                                                                  | Pass — both images built from this checkout; the `revision` label equals the commit            |
| `docker image inspect` on both built images                                                                                                                                                        | The OCI metadata carries the commit SHA, version, date, and source                             |
| `docker compose config` with the image variables unset                                                                                                                                             | Fails closed with a named error                                                                |
| Backend infrastructure test suite (`test_production_compose`, `test_release_workflow`, `test_production_proxy`, `test_production_config`, `test_tls_certificate_tooling`, `test_deployment_guard`) | All passed                                                                                     |
| Workflow YAML parsed; every `run:` script checked with `bash -n`                                                                                                                                   | No syntax error                                                                                |
| Repository review of `compose.production.yml`, `Dockerfile.api`, `Dockerfile.web`, `deploy/caddy/`, `deploy/tls/`, `Makefile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`         | Every claim in section 2 traced to a file and line                                             |
| Review of `docs/architecture/deployment.md`, `docs/operations/*`, ADR 011–015                                                                                                                      | Open decisions confirmed as open; no decision was inferred from a document that leaves it open |
| `git diff --check`                                                                                                                                                                                 | Clean                                                                                          |
| Secret exposure scan of this document                                                                                                                                                              | No secret value, real IP, DNS name, or certificate data; placeholders only                     |

Deliberately **not** run, and why:

- `make prod-up`, `prod-provision`, `prod-migrate`, `prod-bootstrap-owner` — they would start the
  Production stack or touch a database.
- `make prod-caddy-validate`, `tls-validate`, `tls-activate` — they would read real certificate
  and private-key material.
- Any `ssh`, `ping`, `nc`, port scan, or remote command against `market-linux` — the server was
  never contacted.
- Any inspection of `.env` or `.env.*` files, or of any secret value.
- `docker compose up` against `compose.production.yml` — no Production stack was started.
- Publishing a release, pushing an image, or creating a registry package — the release workflow was
  never executed, and no image was pushed anywhere.
