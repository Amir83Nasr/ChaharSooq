# ADR 021 — Discover the deploy version from the published GitHub Release

Date: 2026-11-18 · Status: accepted

## Context

[ADR 018](018-simple-production-deploy.md) made the mutable `latest` image tag the
discovery pointer: the deploy script resolved it to digests and relied on matching
OCI labels to reject a half-published release. That works, but it makes the registry
the source of truth for _which_ release to deploy. [ADR 019](019-release-publication-after-image-verification.md)
already established the stronger signal: the GitHub Release is published last, only
after both images exist, carry the release commit, and have verified digests.

Operators also had to trust an unannotated sequence of log lines and an unconditional
migration run: `migrate` always started, even when the database was already at head,
and the final line did not say what was deployed or which services were healthy.

## Decision

- `deploy/scripts/deploy.sh` with no argument (or with `latest`) reads
  `GET /repos/{CHARSOOQ_GITHUB_REPO}/releases/latest`; a `vMAJOR.MINOR.PATCH`
  argument reads `/releases/tags/{tag}`. Draft and prerelease responses are
  rejected, the tag is validated, and the version tag — never `latest` — is
  resolved to two image digests. The image `version` label must equal the release
  version; when the release target is a full commit SHA, the image `revision`
  label must equal it too. Both images must still come from one release.
- A private repository is supported by exporting `GITHUB_TOKEN` in the operator
  shell. It is passed to curl in a 0600 temporary header file that is removed on
  exit; the token is never stored in Git, the env file, an image, or script output.
  Two explicit `repo@sha256:...` references still bypass GitHub entirely.
- The deploy runs as nine numbered steps with per-step progress and finishes with
  a summary of release, commit, host, migration result, container states, health
  endpoints, duration, and the exact rollback command when the previously running
  version is readable. Container state comes from `docker compose ps`/`docker
inspect`; external probes cover `/api/v1/health`, `/api/v1/ready`, and `/login`.
  Any failed probe or non-running/non-healthy required container fails the deploy.
- Before starting the API, `migrate.py --check` compares the recorded Alembic
  revision with the single head using the migration credential, read-only. The
  one-shot migrate service runs only when a revision is pending. The upgrade still
  holds the ChaharSooq advisory lock; no migration is skipped silently.
- `CHARSOOQ_GITHUB_REPO` is added to `deploy/production.env.example`. Everything
  else in ADR 018 and ADR 019 — digest pinning, role provisioning order, additive
  migrations, secret handling, and the explicit operator step — remains in force.
  The `latest` tag continues to be published as a discovery pointer for other
  consumers; it is no longer the deploy script's discovery source.

## Consequences

- The published Release is the single all-or-nothing deploy signal. A failed CI
  build cannot cause an automatic deploy, and a partially moved `latest` pointer
  cannot select images that disagree with the Release.
- Discovery needs HTTPS access to the GitHub API from the Production host and a
  token for a private repository. Registry-only hosts must choose explicit
  digests; the old no-argument behavior is intentionally gone.
- The migration check adds one short-lived one-shot container. A check error
  fails closed before the API starts; a database already at head avoids a second
  migration container and is reported as such in the summary. An image from
  before `--check` existed is detected by its usage error: the deploy falls back
  to the plain migration runner so a code rollback remains possible.
- The rollback command shown in the summary uses the previous container's image
  label. If that container is gone, the generic `<previous-version>` placeholder
  is printed instead; no rollback is ever performed automatically.

## Alternatives considered

- **Keep the `latest` pointer and only improve the log output.** Rejected: the
  registry pointer is weaker than the Release and would leave the version choice
  outside the verified publication signal.
- **Always run `migrate`, as before.** Rejected: the read-only check is cheap,
  makes the no-op explicit, and keeps the pending case under the same advisory
  lock.
- **Deploy from the GitHub Release body's digest table.** Rejected for now: the
  markdown table is release notes, not an API contract; the version tag plus
  image labels and release commit already fail closed without parsing prose.
