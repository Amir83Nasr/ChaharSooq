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
  single `api`/`web` pair, and verifies container and external health. A specific
  version tag or two explicit digests are also accepted. It prints numbered
  progress and a final health/status summary, is fail-closed, and never reads a
  secret value or removes a volume, database, or image.

## What must stay outside this directory/repository

- Secret files (`postgres_password`, `database_url`, `migration_database_url`,
  `session_secret`, `owner_password`, `parsina_password`) — host path
  `CHARSOOQ_SECRETS_DIR`, default `/etc/charsooq/secrets`.
- TLS certificate/key material and CA files — host path `CHARSOOQ_TLS_DIR`,
  default `/etc/charsooq/tls`.
- Filled `production.env` files with real environment values.

See [AGENTS.md](../AGENTS.md) for the rules, [README.md](../README.md) for the
production stack, and [ADR 018](../docs/adr/018-simple-production-deploy.md)
for why deployment is a single-slot script.
