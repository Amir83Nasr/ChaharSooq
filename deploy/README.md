# `deploy/` — Production runtime material

This directory holds files mounted into the Production stack at runtime. It is
**not** copied into container images (`.dockerignore` excludes `deploy/`) and it
must never contain secret values, private keys, or certificates.

## Contents

- `caddy/` — committed Caddy configuration: the main `Caddyfile`, the shared
  `site.caddy` (which holds the single static `reverse_proxy web:3000`
  upstream), and the three TLS-mode snippets. Mounted read-only into the
  `caddy` container. No upstream-switching file and no reload-driven traffic
  selection remain.
- `tls/validate_certificate.py` — offline validator for a certificate/key pair
  (PEM structure, key match, chain, expiry, SAN, permissions). Prints no key
  material and performs no network access or issuance.
- `tls/activate_certificate.py` — stages a validated pair under
  `versions/<stamp>/` and switches the single `current` symlink atomically for
  rollback-safe activation.
- `../backend/api/scripts/backup_cli.py` — one-shot worker CLI (`plan`, `queue-backup`, `run-once`,
  `prune`, `requests`) for hosts that prefer an external tick over the API's background thread. It
  uses the application role, refuses Staging, and never reads an admin or migration credential. The
  API container already runs the same worker; the CLI is not required by the default stack (see
  [ADR 023](../docs/adr/023-in-app-backup-and-data-restore.md)).
- `production.env.example` — template for the non-secret deployment variables
  required by `compose.production.yml` (`CHARSOOQ_*`), including the GitHub
  repository used for release discovery, the image repositories, the single
  edge network/web address, and configuration-driven protocol/TLS (HTTP-only or
  HTTPS). Copy it **outside** the repository, fill the approved values, and
  source it in the operator shell. Do not guess or auto-generate network/TLS
  values.
- `scripts/deploy.sh` — the one Production deploy entry point, run on the host
  (or over SSH via `make prod-deploy SSH_HOST=...`). With no argument it reads the
  newest published GitHub Release, resolves its version tag to two image
  digests, checks that both images report that release version and commit, then
  pulls, provisions, checks migrations (applying only when pending), starts the
  single `api`/`web` pair, and verifies container and external health. It first
  compares the configured database image major with the on-disk `PG_VERSION`
  before **and** immediately after release discovery, refuses to start if they
  differ, and prints the ADR 028 cutover commands when a major bump is pending. A
  specific version tag or two explicit digests are also accepted. It prints
  numbered progress and a final health/status summary, is fail-closed, and never
  reads a secret value or removes a volume, database, or image.
- `scripts/pg_upgrade_drill.sh` — rehearses the 18 → 19 logical upgrade against
  throwaway containers and volumes only, using a full administrative-role dump
  supplied by the operator. It compares version, data directory, migration
  revision and row counts, and removes only its own scratch resources (see
  [ADR 028](../docs/adr/028-postgresql-19-upgrade-readiness.md)).
- `scripts/pg19_cutover.sh` — performs the real 18 → 19 data cutover on the server
  against the `pgdata` volume, after the rehearsal passed and the stack is
  stopped. It moves the 18 datadir to `/var/lib/postgresql/rollback/18` on the
  **same volume** (required: the 18+ image refuses to start when it sees an old
  datadir at `/var/lib/postgresql/*/docker`), restores the verified dump into a
  fresh 19 cluster, checks the migration revision and row counts, and never
  deletes a datadir or volume. Re-running it after a successful cutover is a
  no-op. See [the cutover runbook](../docs/pg19-cutover-runbook.md).
- [`../docs/pg19-cutover-runbook.md`](../docs/pg19-cutover-runbook.md) — the
  operator checklist for the Production 18 → 19 upgrade: preflight, full dump,
  rehearsal, stop writes, cutover, config, deploy, verification, fresh backup and
  rollback.
- `scripts/release_watch.sh` + `systemd/charsooq-release-watch.{service,timer}` —
  an optional outbound-only auto-deploy agent. Every 5 minutes it reads the newest
  published GitHub Release, compares it with the last deployed tag in
  `/var/lib/charsooq/last-deployed-release`, and calls `deploy.sh` only for a new
  published, non-draft, non-prerelease tag. State is written only after a
  successful deploy, so failures retry on the next tick. Install with
  `make prod-watch-install` on the host ([ADR 033](../docs/adr/033-automatic-release-polling-deploy.md)).

## What must stay outside this directory/repository

- Secret files (`postgres_password`, `database_url`, `migration_database_url`,
  `session_secret`, `owner_password`, `parsina_password`) — host path
  `CHARSOOQ_SECRETS_DIR`, default `/etc/charsooq/secrets`.
- TLS certificate/key material and CA files — host path `CHARSOOQ_TLS_DIR`,
  default `/etc/charsooq/tls`.
- Filled `production.env` files with real environment values.

## One-command deploy without GitHub access

If the host cannot reach the GitHub API, leave `CHARSOOQ_GITHUB_REPO` empty and
copy the two `repo@sha256:<digest>` references from the GitHub Release body into
`CHAHARSOQ_API_IMAGE` / `CHAHARSOQ_WEB_IMAGE` in `production.env`. `deploy.sh`
then uses those digest-pinned references and skips discovery, so `make
prod-deploy` stays a single command. For remote deploys over SSH, set
`SSH_HOST=... PROD_REMOTE_DIR=<checkout-path>` (the remote path defaults to
`/opt/charsooq`).

See [AGENTS.md](../AGENTS.md) for the rules, [README.md](../README.md) for the
production stack, and [ADR 018](../docs/adr/018-simple-production-deploy.md)
for why deployment is a single-slot script.
