# `deploy/` — Production runtime material

This directory holds files mounted into the Production stack at runtime. It is
**not** copied into container images (`.dockerignore` excludes `deploy/`) and it
must never contain secret values, private keys, or certificates.

## Contents

- `caddy/` — committed Caddy configuration: the main `Caddyfile`, the shared
  site body, the two TLS-mode snippets (`organization` and `internal-ca`), and
  the generated `active-upstream.caddy` that selects the active Blue-Green slot.
  Mounted read-only into the `caddy` container.
- `tls/validate_certificate.py` — offline validator for a certificate/key pair
  (PEM structure, key match, chain, expiry, SAN, permissions). Prints no key
  material and performs no network access or issuance.
- `tls/activate_certificate.py` — stages a validated pair under
  `versions/<stamp>/` and switches the single `current` symlink atomically for
  rollback-safe activation.
- `production.env.example` — template for the non-secret deployment variables
  required by `compose.production.yml` (`CHARSOOQ_*`), including Blue-Green slot
  edge values and **configuration-driven protocol/TLS** (HTTP-only or HTTPS).
  Copy it **outside** the repository, fill the approved values, and source it
  in the operator shell. Do not guess or auto-generate network/TLS values.
- `scripts/deploy.sh` — the automated Production deploy entry point called by
  the release workflow's `deploy` job on the self-hosted runner. It performs a
  Blue-Green deployment by digest after required-variable/path preflight: it
  starts the inactive slot, verifies revision/health/smoke checks, switches
  `caddy/active-upstream.caddy` with a graceful reload, runs **protocol-aware**
  external probes (HTTP or HTTPS from configuration), and keeps the previous
  slot running for rollback. It never reads a secret value and never removes a
  volume, database, or image.
- `runner/` — **preparation only** for the repository-scoped self-hosted runner
  (`charsooq-production` label): non-secret templates and read-only preflight
  helpers. No runner is installed/registered and no token/secret is stored here.
  See [docs/operations/self-hosted-runner.md](../docs/operations/self-hosted-runner.md).

## What must stay outside this directory/repository

- Secret files (`postgres_password`, `database_url`, `migration_database_url`,
  `session_secret`, `owner_password`, `parsina_password`) — host path
  `CHARSOOQ_SECRETS_DIR`, default `/etc/charsooq/secrets`.
- TLS certificate/key material and CA files — host path `CHARSOOQ_TLS_DIR`,
  default `/etc/charsooq/tls`.
- Filled `production.env` files with real environment values.

See [docs/architecture/deployment.md](../docs/architecture/deployment.md),
[docs/operations/production-runbook.md](../docs/operations/production-runbook.md),
[docs/operations/tls-certificate-lifecycle.md](../docs/operations/tls-certificate-lifecycle.md),
and [docs/operations/release-management.md](../docs/operations/release-management.md).
