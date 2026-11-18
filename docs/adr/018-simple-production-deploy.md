# ADR 018 — Simple single-slot Production deploy

Date: 2026-11-18 · Status: accepted

## Context

[ADR 016](016-ci-cd-deploy-job.md) added an event-driven deploy job and
[ADR 017](017-blue-green-deployment.md) replaced it with a Blue-Green pair. Both
are fully implemented and contract-tested in the repository, but neither has
ever run on `market-linux`: deployment is blocked on a registered self-hosted
runner, `/etc/charsooq/production.env`, two operator-approved edge CIDRs and
fixed IPs, a state directory, and an upstream-switching file. The stack is not
live yet, so changing the mechanism costs nothing in production.

The actual requirement is modest: publish images from a release
([ADR 015](015-container-image-release-and-publishing.md)), then let an operator
deploy one version to the server with a single, easy command. The Blue-Green
machinery adds installation and operational burden without being required for
correctness: it still shares one database, still needs additive migrations, and
still does not guarantee zero dropped requests.

## Decision

- **One deployable pair.** `compose.production.yml` keeps `db`, `provision`,
  `migrate`, and `caddy` as the shared base plus a single `api`/`web` pair on one
  operator-approved `edge` network. No compose profiles, no slot IPs, no
  `active-upstream.caddy`, and no `/etc/charsooq/state`.
- **One deploy command.** `make prod-deploy VERSION=v1.2.3` runs
  `deploy/scripts/deploy.sh` on the host, or over SSH when `SSH_HOST` is set. A
  manual release `workflow_dispatch` still publishes images; it no longer
  deploys.
- **Still digest-pinned and fail-closed.** The script resolves a version tag to
  two image digests with `docker buildx imagetools inspect` before changing
  anything, validates every required value and secret file, then runs
  `pull → provision → migrate → up -d → external health probe`. It never removes
  a volume, database, or image. Two explicit `repo@sha256:<digest>` references
  are also accepted.
- **A discoverable newest release.** The release workflow publishes a mutable
  `latest` tag on both images as a _discovery pointer only_; the version and
  `sha-<commit>` tags stay write-once. Publishes are serialized so the pointer
  always names the newest completed release. With no argument, the deploy
  script resolves `latest` to two digests, reads the OCI `version` and
  `revision` labels from both images, and refuses to continue if they differ —
  so a half-published release can never be deployed mixed. This supersedes the
  "no `latest`" clause of [ADR 015](015-container-image-release-and-publishing.md):
  the pointer is never a deployment reference, and the resolved digest, version,
  and commit are logged for audit.
- **No self-hosted runner.** The `deploy` job and the `charsooq-production`
  runner label are removed from `release.yml`; nothing in CI can reach the
  Production host. All previously documented secret, network, migration, and
  exposure rules remain in force.
- **Rollback is the same command with the previous version.** No automatic data
  rollback is performed; a code rollback is not a data rollback
  ([ADR 014](014-production-backup-and-recovery.md)).

## Consequences

- Deployment requires only a filled `production.env`, the six file-backed
  secrets, and IT-approved IP/DNS values on the host. There is no runner to
  register, no second subnet/IP pair, and no state file to recover.
- No version has to be typed: `make prod-deploy` deploys the newest release,
  while `make prod-deploy VERSION=v1.2.3` still pins a specific one.
- A deploy replaces the running `web` container, so a brief connection error is
  possible. Caddy receives `SIGUSR1` after `up` to refresh its upstream DNS;
  zero dropped requests is not guaranteed.
- Migrations still run against the shared database before the new API starts.
  They must remain additive or expand-compatible with the currently serving
  code; contracting changes need the expand/contract process or a maintenance
  window.
- Sessions remain database-backed and the cookie contract is unchanged, so a
  session survives a deploy. `SESSION_COOKIE_SECURE` stays `false` for the
  current HTTP-only internal deployment; enabling HTTPS is a separate,
  coordinated change.
- ADR 016 and ADR 017 are superseded by this decision and are kept only as a
  record of the rejected, more complex design.

## Alternatives considered

- **Keep Blue-Green, remove only the runner.** Rejected: two edge networks, two
  fixed IPs, the state file, and upstream switching would still need to be
  configured and operated.
- **Automate the simple script from a runner.** Rejected: runner registration
  and GitHub environment protection rules are the largest setup burden and are
  unnecessary for a one-command deploy.
- **Deploy on every push to `main`.** Rejected by ADR 015: a branch push is not
  a release.
