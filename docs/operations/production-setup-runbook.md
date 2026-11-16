# Production setup runbook — ChaharSooq (Blue-Green, self-hosted deploy)

Status: **runbook/procedure only**. Nothing in this repository has been executed on `market-linux`, no
Production stack has been started, no secret has been created, no runner has been registered, and no
Production data/network/volume/image has been changed.

Related: [production-runbook.md](production-runbook.md) ·
[self-hosted-runner.md](self-hosted-runner.md) ·
[release-management.md](release-management.md) ·
[rollback.md](rollback.md) ·
[infrastructure-readiness.md](infrastructure-readiness.md) ·
[it-requirements.md](it-requirements.md) ·
[tls-certificate-lifecycle.md](tls-certificate-lifecycle.md) ·
[backup-and-recovery.md](backup-and-recovery.md) ·
[deployment.md](../architecture/deployment.md) ·
[ADR 016](../adr/016-ci-cd-deploy-job.md) ·
[ADR 017](../adr/017-blue-green-deployment.md)

## 1. Scope and safety boundaries

- **Network:** Production host is inside the private network with outbound-only access to
  GitHub/GHCR. No inbound port, webhook, port forwarding, or public IP is opened for deployment.
- **Trigger:** only stable `release.published` (or explicit `workflow_dispatch` with `deploy=true` for
  an existing stable published release). `push` to `main` is not a Production release.
- **Deployment model:** Blue-Green with shared base (`db`, `provision`, `migrate`, `caddy`) and two
  slots (`blue`/`green`), digest-only images, traffic switch via
  `deploy/caddy/active-upstream.caddy`, previous slot kept for rollback.
- **No destructive actions:** never run `docker compose down -v`, `docker volume prune`,
  `docker system prune`, or delete volumes/databases/images during setup or deploy.

## 2. Prerequisites (must be confirmed before setup)

| Area            | Requirement                                                                                                              | Evidence                                                           |
| --------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Host/IT         | `market-linux` approved, Ubuntu/Docker/Compose/systemd ready, clock/NTP healthy, approved bind IP/host/subnets available | IT confirmation + host checks                                      |
| DNS/TLS         | `CHARSOOQ_SITE_HOST` resolves as approved; certificate strategy/material prepared and validated per TLS lifecycle docs   | `tls-validate`/Caddy validation records                            |
| Secrets         | Six Production secret files prepared outside repo with correct ownership/mode; no secret in Git                          | Host file metadata checks (no content reads in docs/logs)          |
| Images/registry | Release images published to GHCR with digests; host can pull public images outbound                                      | Release body digests + pull test in approved window                |
| GitHub controls | Protected releases/tags, `production` environment policy, Actions/fork restrictions, self-hosted runner policy           | Repository/environment settings review                             |
| Runner          | Dedicated repository-scoped runner `charsooq-production` registered and healthy (outbound-only)                          | [self-hosted-runner.md](self-hosted-runner.md) activation evidence |

## 3. Host paths and configuration files

Prepare these outside the repository (paths are defaults; adjust only by approved decision):

- `/etc/charsooq/production.env` — **non-secret** deployment values copied from
  [`deploy/production.env.example`](../../deploy/production.env.example). Required for Blue-Green and
  protocol-aware deploy: `CHARSOOQ_PROXY_BIND_IP`, `CHARSOOQ_SITE_HOST`,
  `CHARSOOQ_EDGE_BLUE_SUBNET`, `CHARSOOQ_WEB_BLUE_EDGE_IP`, `CHARSOOQ_EDGE_GREEN_SUBNET`,
  `CHARSOOQ_WEB_GREEN_EDGE_IP`, `CHARSOOQ_PUBLIC_SCHEME` (`http`/`https`), `CHARSOOQ_TLS_MODE`
  (`none` for HTTP-only, `organization`/`internal-ca` for HTTPS), `CHARSOOQ_CADDY_AUTO_HTTPS`, and
  release image refs/digests when deploying manually. `CHARSOOQ_CA_FILE` is required for HTTPS
  external probes. **Do not guess or auto-generate IPs/subnets/TLS values and do not modify
  Production env files automatically.** Missing required values must stop deployment before any change.
- `/etc/charsooq/secrets/*` — `postgres_password`, `database_url`, `migration_database_url`,
  `session_secret`, `owner_password`, `parsina_password` (ownership/mode per deployment/runbook docs).
  The deploy/runner account must **not** read secret contents.
- `/etc/charsooq/state/` — directory writable by the deploy/runner account; deploy writes
  `deploy-state.env` here (`CHARSOOQ_STATE_DIR`, default `/etc/charsooq/state`).
- `/etc/charsooq/tls/` — certificate material outside repo (mode-dependent; unused for HTTP-only `none`).
- Deployment checkout (e.g. `/opt/charsooq`) — contains released `compose.production.yml` and
  `deploy/scripts/deploy.sh`. `deploy/caddy/active-upstream.caddy` must be a regular file
  **writable** by the deploy/runner account for atomic traffic switch/reload (exact path:
  `${CHARSOOQ_ACTIVE_UPSTREAM_FILE:-<checkout>/deploy/caddy/active-upstream.caddy}`). Keep runner
  write access limited to these required paths only.

## 4. Preflight and validation (read-only / structural)

Run from an approved checkout on the host:

```bash
# Read-only runner/deploy host hints (no install/register, no secret reads).
# Fails on missing green slot variables and other required deploy blockers.
bash deploy/runner/preflight.sh [path/to/runner.env]

# Structural compose validation only (documentation values; not a production proof)
make prod-config
```

`deploy/scripts/deploy.sh` performs fail-closed checks before any state-changing action
(no `compose up/run`, no upstream rewrite, no Caddy reload, no state write): required
image/host/slot/protocol variables, green edge variables, writable
`active-upstream.caddy`, writable/creatable state path, and required external-probe
configuration (`curl`, `CHARSOOQ_CA_FILE` for HTTPS). If checks fail, deployment stops.

With real non-secret deployment values exported/sourced (and image refs as required), validate:

```bash
docker compose -f compose.production.yml --profile blue config --quiet
docker compose -f compose.production.yml --profile green config --quiet
```

Do not treat structural validation as proof that secrets, TLS material, DNS, firewall policy, or
registry access are correct.

## 5. First Production bring-up (manual fallback / controlled window)

Follow [production-runbook.md](production-runbook.md) for exact commands, checks, and stop conditions.
High-level order:

1. **Preflight and backups:** confirm host/network/disk/time, secret file metadata, TLS material,
   approved subnets/IPs, and take/verify backup before any migration on existing data.
2. **Start shared base:** bring up `db`, run `provision`, run `migrate` (locked, additive-compatible),
   and start `caddy`.
3. **Start one active slot:** pull/start the selected slot images by digest (`blue` by default for first
   controlled start), verify slot health/readiness and web/login probes.
4. **Verify end-to-end:** HTTPS/TLS chain and SAN, HSTS behavior, login/session, same-origin API path,
   and absence of unintended published ports/services.
5. **Record state:** ensure `deploy/caddy/active-upstream.caddy` and `/etc/charsooq/state/deploy-state.env`
   reflect the active slot and release identity.

## 6. Enable automated Blue-Green deployments

1. Complete runner preparation and activation per [self-hosted-runner.md](self-hosted-runner.md)
   (repository-scoped, label `charsooq-production`, outbound-only, systemd/autostart, least privilege).
2. Ensure GitHub `production` environment and release protections are in place; PR/untrusted workflows
   must not run on the Production runner.
3. Confirm `/etc/charsooq/production.env`, `/etc/charsooq/state`, deployment checkout, and active
   upstream file permissions allow the runner/deploy script to operate without reading secrets.
4. Run a controlled release deploy in an approved window and monitor the `Release Images` workflow:
   `verify → publish → deploy` (self-hosted). Validate slot verification, traffic switch, external
   probes, and persisted state.

## 7. Post-deploy and steady-state checks

- Confirm active slot, release tag/version/SHA, and image digests match the published release.
- Confirm previous slot remains available for rollback (when healthy and compatible).
- Monitor Caddy/API/Web/DB health and logs; keep container log rotation as configured.
- Rehearse rollback procedure from [rollback.md](rollback.md) during a controlled exercise before
  relying on automated recovery in production incidents.

## 8. Temporary/known limitations (must be tracked)

- `SESSION_COOKIE_SECURE` is currently `false` for temporary HTTP-only internal deployment; keep this
  value until HTTPS is enabled and approved (no migration to HTTPS in this stage).
- Caddy supports explicit HTTP-only mode via configuration (`CHARSOOQ_PUBLIC_SCHEME=http`,
  `CHARSOOQ_TLS_MODE=none`, `CHARSOOQ_CADDY_AUTO_HTTPS=off`, `CHARSOOQ_HSTS_MAX_AGE=0`): no TLS,
  no HTTP→HTTPS redirect, no HSTS, and external probes run over HTTP. HTTPS remains configurable for
  the future by approved config/material changes only.
- Graceful Caddy reload is traffic-gated but not a strict zero-dropped-request guarantee.
- Shared-database migrations must remain additive/expand-compatible during Blue-Green overlap.
- GHCR is assumed public for pull access in the current workflow design; private images require a
  separate, approved credential model (not added here).
- Automated deploy/runner activation has not been executed on `market-linux`.

## 9. Migration from single-slot to Blue-Green (operational)

**Service/command changes:** legacy services `api`/`web` are replaced by slot services
`api-blue`/`web-blue` and `api-green`/`web-green` (profiles `blue`/`green`); shared base remains
`db`, `provision`, `migrate`, `caddy`. Manual operations must target the active slot/profile
(e.g. `docker compose -f compose.production.yml --profile <active> ps`,
`up -d --no-build <db|caddy|api-<slot>|web-<slot>>`, logs/exec for `api-<slot>`/`web-<slot>`).

**Environment variables:** add required green edge values `CHARSOOQ_EDGE_GREEN_SUBNET` and
`CHARSOOQ_WEB_GREEN_EDGE_IP` (approved, conflict-checked; never guessed). Legacy
`CHARSOOQ_EDGE_SUBNET`/`CHARSOOQ_WEB_EDGE_IP` are accepted only as blue compatibility inputs by
`deploy/scripts/deploy.sh`; keep explicit blue vars in the canonical env file. Add protocol config
(`CHARSOOQ_PUBLIC_SCHEME`, `CHARSOOQ_TLS_MODE`, `CHARSOOQ_CADDY_AUTO_HTTPS`, `CHARSOOQ_HSTS_MAX_AGE`,
and `CHARSOOQ_CA_FILE` when HTTPS).

**Preflight gates:** `bash deploy/runner/preflight.sh [env]` must report no hard failures (especially
green vars and writable `active-upstream.caddy`/state path). `deploy/scripts/deploy.sh` stops before
any compose/state change if required vars/paths/protocol probe prerequisites are missing.

**State/upstream:** `deploy/caddy/active-upstream.caddy` selects the active slot and is rewritten
atomically on deploy; `/etc/charsooq/state/deploy-state.env` records active/inactive slot and release
identity. First Blue-Green cutover must be performed in an approved maintenance window with verified
backups and a rollback plan; do not auto-modify Production env or server state.
