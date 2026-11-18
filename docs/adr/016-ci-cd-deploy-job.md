# ADR 016 — Event-driven CI/CD deploy job

Date: 2026-11-16 · Status: superseded by [ADR 018](018-simple-production-deploy.md)

> Kept as a record of the rejected runner/Blue-Green path. Do not implement from
> this document; [ADR 018](018-simple-production-deploy.md) is the current design.

## Context

[ADR 015](015-container-image-release-and-publishing.md) made a published GitHub Release the only
trigger that publishes the API and web images, with both digests recorded in the release body.
Publishing still did not deploy anything: Production promotion was a manual, operator-run
procedure.

The network is fixed:

- GitHub has no inbound access to the company server.
- The Production host is inside the company's private network.
- The host can make outbound connections to the internet, GitHub, and GHCR.
- No new inbound port may be opened.
- No direct webhook, port forwarding, or public IP may be used.
- No scheduled polling for a new release is wanted.

The images are published to GHCR as public images, so the host can pull them without a PAT. The
repository is private, and the Production host already runs Docker Engine and Compose v2.

## Decision

- **A published, stable GitHub Release is the only trigger that deploys.** The `deploy` job is
  part of [`.github/workflows/release.yml`](../../.github/workflows/release.yml) and runs on
  `release: published`. There is no `push`, `schedule`, or polling trigger.
- **Draft and prerelease releases never deploy.** The `publish` job already rejects them, so the
  `deploy` job cannot start for them. The job's `if` also states the stable-release condition
  explicitly, so the guard does not depend on a single step.
- **A manual run is not a second authorization.** `workflow_dispatch` builds and publishes by
  default. It deploys only when the new `deploy` input is explicitly `true`, and the named release
  must still be published and stable.
- **The deploy job runs only on the dedicated self-hosted runner.** `runs-on` is
  `[self-hosted, Linux, charsooq-production]`. The runner keeps an outbound connection to GitHub; no
  inbound port, webhook, or public IP is involved. The workflow has no `pull_request` trigger, so
  pull requests never reach the Production runner.
- **The deploy job waits for both images.** It declares `needs: [publish]` and receives the real
  digests from the publish job outputs. A tag is never passed to Production.
- **One deployment at a time.** The job has `concurrency.group: deploy-production` and
  `cancel-in-progress: false`. A queued release waits instead of racing the active deployment.
- **The job uses the `production` environment and `contents: read`.** It references no GitHub
  secret. The non-secret deployment values (`CHARSOOQ_PROXY_BIND_IP`, `CHARSOOQ_SITE_HOST`,
  `CHARSOOQ_EDGE_SUBNET`, `CHARSOOQ_WEB_EDGE_IP`, TLS and secret-directory paths) come from
  `/etc/charsooq/production.env` on the host.
- **The host pulls public GHCR images by digest.** No registry credential is stored by the
  workflow. If the images ever become private, this decision must be revisited with a host-side
  read-only credential.
- **The deploy script is the only automated Production path.**
  [`deploy/scripts/deploy.sh`](../../deploy/scripts/deploy.sh) is fail-closed and health-gated:
  1. it accepts only `repository@sha256:<digest>` references;
  2. it verifies the published `org.opencontainers.image.revision` label against the release
     commit;
  3. it runs `provision` and the locked `migrate` before the new API starts;
  4. it starts the API, then web, then re-points Caddy;
  5. it verifies real health probes (`/ready`, `/login`, and an optional external HTTPS probe);
  6. on failure it restores the previously running image references.
- **Nothing is removed.** The script never runs `docker compose down -v`, `docker volume prune`,
  or `docker system prune`. Volumes, databases, and old images are kept for rollback.
- **The job checks out the released commit.** The compose file and deploy script come from the
  same commit that produced the images.

## Consequences

- The workflow is configured, but it cannot run until the self-hosted runner is registered with
  the `charsooq-production` label and `/etc/charsooq/production.env` exists on the host. Neither is part
  of this repository.
- The deploy mechanism is superseded by [ADR 017](017-blue-green-deployment.md): the automated path
  is now a Blue-Green deployment with slot profiles, a switchable Caddy upstream, and a
  traffic-gated rollback, while preserving the same trigger, runner, digest, and security
  constraints defined here.
- A migration runs while the previous API is still serving. It must therefore be additive or
  expand-compatible with the old code. An incompatible migration needs the expand/contract
  procedure or a maintenance window; a code rollback is not a data rollback
  ([ADR 014](014-production-backup-and-recovery.md)).
- The deploy job logs image references, statuses, and probe results. It never prints an
  environment file, a secret value, or a token.
- The runner account must be able to read `/etc/charsooq/production.env` and to write
  `/etc/charsooq/state`. The file contains no secret values; the six secret files stay
  root/UID-owned and are mounted by the Docker daemon, not read by the runner.
- The optional `CHARSOOQ_CA_FILE` enables the external HTTPS probe in the deploy script. When
  it is unset, the script relies on the container healthchecks and logs a warning.
- The runner's Docker access is root-equivalent on the host. The runner account, its group
  membership, and the `production` environment protection rules are IT-owned hardening tasks.
- If GHCR images become private, the host needs a read-only pull credential and the workflow
  constants change. The digest remains the deployment identity.

## Alternatives considered

- **A separate `deploy.yml` triggered by `workflow_run`.** Rejected: it duplicates the release
  guard and needs an artifact download or a second release lookup. One workflow keeps the
  publish-to-deploy dependency explicit.
- **A scheduled poll for new releases.** Rejected by the network requirements and by the
  event-driven design.
- **A direct webhook or SSH push from GitHub.** Rejected: GitHub has no inbound path to the host.
- **Deploying on every push to `main`.** Rejected by ADR 015: a branch push is not a release.
- **A full blue-green pair now.** Rejected for this change: it requires Compose, Caddy, and
  network changes that are not yet configured, and the current task is the event-driven
  workflow. The health-gated replace preserves the previous release on failure and is the
  safest step that fits the existing stack.
