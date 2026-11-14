# ADR 015 — Container image release and publishing

Date: 2026-11-14 · Status: accepted

## Context

Production runs the Docker Compose stack in [`compose.production.yml`](../../compose.production.yml) on
`market-linux`. Before this decision the repository had two Dockerfiles and a CI workflow, but no
release artifact at all:

- No workflow built or published an image. `grep` for `ghcr`, `docker/login-action`, and
  `docker/build-push-action` under `.github/` returned nothing.
- The Compose file defaulted to the mutable local tags `charsooq-api:production` and
  `charsooq-web:production`. An unset image reference therefore deployed whatever happened to sit in
  the local image cache, and the first rehearsal already found a stale `charsooq-api:production` image
  that predated `provision_database_roles.py`.
- Neither Dockerfile carried a `revision` label, so a deployed image could not be traced back to a
  commit.
- `deployment.md` already required that Production "builds its image once from the approved commit,
  tags it immutably … and deploys that exact image **by digest**", and that the Git commit SHA is the
  cross-environment release identity. Nothing implemented that.

The organization has not yet answered the registry question (IT checklist 4.6). The decision must
therefore work today with the credentials the platform already provides, and must not depend on a
secret that does not exist yet.

## Decision

- **A published GitHub Release is the only trigger that publishes images.** The workflow
  [`.github/workflows/release.yml`](../../.github/workflows/release.yml) runs on `release: published`.
  There is deliberately no `push` trigger: a push to `main` is never a Production release. A manual
  `workflow_dispatch` run is allowed but must name an existing, published, non-prerelease release, so
  the button is not a second authorization.
- **The release tag is `v<version>`.** The image tag is the version without the leading `v`.
  Requiring the `v` keeps the release tag and the image tag in a one-to-one relation, so two
  different release tags can never name the same image tag.
- **GitHub Container Registry is the default registry**, because `GITHUB_TOKEN` authenticates to it
  without creating a new secret. The registry, the namespace, and the image names are workflow-level
  constants in `release.yml`; another registry needs a credential and an IT decision.
- **Both images come from one commit.** The release job checks out the release tag, verifies that the
  checked-out commit is the tag's commit, and builds `Dockerfile.api` and `Dockerfile.web` from that
  single checkout. The CI suite runs against that same commit before the publish job starts. One
  release never produces images from two commits.
- **Every image gets two tags: the release version and the commit SHA.** The version tag is the
  release tag without a leading `v`; the SHA tag is `sha-<full-commit-sha>`. There is no `latest`
  and no other moving tag. The workflow refuses to publish either of them a second time, so a
  release tag is written once _by this workflow_.
- **The registry does not guarantee that.** GitHub Container Registry has no immutable-tag setting:
  a tag is a pointer, and a push from anywhere can move it. The workflow's check is therefore a
  guard, not a guarantee, and a race remains between the check and the push.
- **The digest is the deployment identity.** The workflow records both digests in the release body,
  in the run summary, and in a `release-images.json` artifact. Production selects images by
  `repository@sha256:<digest>`; a tag is never the deployment reference, because a digest is a
  content address and a tag is only a name.
- **Every image carries OCI metadata**: `org.opencontainers.image.revision` (the commit SHA),
  `.version`, `.created`, and `.source`, plus title, description, vendor, and license. The workflow
  reads the revision label back from the published image and fails the release when it does not
  match the release commit, so the commit link is proven rather than assumed.
- **Provenance and SBOM travel with the image.** BuildKit attaches a SLSA provenance attestation and
  an SPDX SBOM to the published image index, and GitHub additionally stores a build provenance
  attestation for the image digest. The two are stored separately and are checked with different
  commands.
- **`compose.production.yml` requires the image reference.** `CHARSOOQ_API_IMAGE` and
  `CHARSOOQ_WEB_IMAGE` have no default: an unset or moving reference fails the stack instead of
  deploying a stale local image. `pull_policy: missing` makes Compose fetch the published image when
  it is not cached.
- **The host build remains a recorded fallback, not the target.** `make prod-build` builds from the
  current checkout, tags by commit, and stamps the same OCI metadata, so even the fallback image says
  which commit it came from. It is never the Production release path.
- **The release workflow runs the repository checks first.** `ci.yml` is reusable, and the release job
  waits for it, so an image is never published from a commit that did not pass the checks. The
  reusable workflow receives the release tag, so the checks run against the published commit and
  not against `main`.
- **Every action is pinned to a full commit SHA.** A publishing workflow must not depend on a
  movable action tag. The version behind each pin is recorded in the workflow file and in
  [release-management.md](../operations/release-management.md).

## Consequences

- A release is reproducible and auditable: the release body names the commit and both digests, and any
  deployed image can be traced back to a commit with `docker image inspect`.
- Publishing needs no new secret. `GITHUB_TOKEN` with `packages: write` is sufficient.
- The registry choice is still open. Moving to another registry means changing the workflow constants
  and adding a credential, which is an IT-owned change.
- The GitHub Actions runner must be able to reach the registry. On an air-gapped or proxied network,
  the publish job fails and the host-build fallback applies.
- **A tag is written once, not immutable.** The workflow refuses to publish over a tag it already
  wrote, but the registry does not enforce that. A push from another client inside the window
  between the check and the push could still move a tag. The digest is the authoritative reference,
  and Production always deploys by digest, so a moved tag cannot change what Production runs — but
  it can mislead a human who deploys by tag.
- A re-run of a release that already pushed one of its images therefore fails instead of overwriting.
  A half-finished publish cannot simply be retried: a registry administrator has to delete the
  half-published tag, or the release is republished under a new version.
- Staging still deploys through the Vercel/FastAPI Cloud Git integration and does not consume these
  images. The commit SHA remains the shared release identity between the two environments.
- The workflow has never been executed against a real release. Every property above is verified by
  the repository's own tests and by an offline review, not by a published image.

## Alternatives considered

- **Publish on every push to `main`.** Rejected: it makes a branch push a release and gives no
  human approval point.
- **Publish with a version tag only.** Rejected: a version tag is still a mutable name, and it says
  nothing about which commit produced the bytes.
- **Publish with `latest`.** Rejected: `latest` cannot be tied to a commit or audited.
- **Rely on the registry to make the tags immutable.** Rejected for now: GitHub Container Registry
  has no such feature, and no other registry has been approved. If IT names a registry with
  immutable tags, the guard step becomes a backstop instead of the only protection.
- **A self-hosted runner or a deploy workflow over SSH.** Deferred: deploy access is an open IT
  decision, and publishing is independent of it.
- **A private registry with a dedicated service account.** Deferred until IT names a registry. The
  workflow constants make it a configuration change, not a redesign.
