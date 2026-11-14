# `deploy/` — Production runtime material

This directory holds files mounted into the Production stack at runtime. It is
**not** copied into container images (`.dockerignore` excludes `deploy/`) and it
must never contain secret values, private keys, or certificates.

## Contents

- `caddy/` — committed Caddy configuration: the main `Caddyfile`, the shared
  site body, and the two TLS-mode snippets (`organization` and `internal-ca`).
  Mounted read-only into the `caddy` container.
- `tls/validate_certificate.py` — offline validator for a certificate/key pair
  (PEM structure, key match, chain, expiry, SAN, permissions). Prints no key
  material and performs no network access or issuance.
- `tls/activate_certificate.py` — stages a validated pair under
  `versions/<stamp>/` and switches the single `current` symlink atomically for
  rollback-safe activation.
- `production.env.example` — template for the non-secret deployment variables
  required by `compose.production.yml` (`CHARSOOQ_*`). Copy it **outside** the
  repository, fill the approved values, and source it in the operator shell.

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
