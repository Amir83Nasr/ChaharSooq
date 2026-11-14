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
- **GitHub Container Registry is the default registry**, because `GITHUB_TOKEN` authenticates to it
  without creating a new secret. The registry and namespace are workflow variables, so a different
  registry can be substituted once IT approves one.
- **Both images come from one commit.** The release job checks out the release tag, verifies that the
  checked-out commit is the tag's commit, and builds `Dockerfile.api` and `Dockerfile.web` from that
  single checkout. One release never produces images from two commits.
- **Every image gets two immutable tags: the release version and the commit SHA.** The version tag is
  the release tag without a leading `v`; the SHA tag is `sha-<full-commit-sha>`. There is no `latest`
  and no other moving tag. An existing version tag stops the run before anything is pushed, so a
  release tag is written once.
- **Every image carries OCI metadata**: `org.opencontainers.image.revision` (the commit SHA),
  `.version`, `.created`, and `.source`, plus title, description, vendor, and license. The workflow
  reads the revision label back from the published image and fails the release when it does not match
  the release commit, so the commit link is proven rather than assumed.
- **Provenance and SBOM travel with the image.** BuildKit attaches a SLSA provenance attestation and
  an SPDX SBOM to the published image index, and GitHub additionally stores a build provenance
  attestation for the image digest.
- **The digest is the deployment identity.** The workflow records both digests in the release body,
  in the run summary, and in a `release-images.json` artifact. Production selects images by
  `repository@sha256:<digest>`; a tag is never the deployment reference.
- **`compose.production.yml` requires the image reference.** `CHARSOOQ_API_IMAGE` and
  `CHARSOOQ_WEB_IMAGE` have no default: an unset or moving reference fails the stack instead of
  deploying a stale local image. `pull_policy: missing` makes Compose fetch the published image when
  it is not cached.
- **The host build remains a recorded fallback, not the target.** `make prod-build` builds from the
  current checkout, tags by commit, and stamps the same OCI metadata, so even the fallback image says
  which commit it came from. It is never the Production release path.
- **The release workflow runs the repository checks first.** `ci.yml` is reusable, and the release job
  waits for it, so an image is never published from a commit that did not pass the checks.

## Consequences

- A release is reproducible and auditable: the release body names the commit and both digests, and any
  deployed image can be traced back to a commit with `docker image inspect`.
- Publishing needs no new secret. `GITHUB_TOKEN` with `packages: write` is sufficient.
- The registry choice is still open. Moving to another registry means changing the workflow variables
  and adding a credential, which is an IT-owned change.
- The GitHub Actions runner must be able to reach the registry. On an air-gapped or proxied network,
  the publish job fails and the host-build fallback applies.
- The version tag is immutable, so re-running a failed publish needs a new version or an explicit
  deletion of the half-published tag by a registry administrator.
- Staging still deploys through the Vercel/FastAPI Cloud Git integration and does not consume these
  images. The commit SHA remains the shared release identity between the two environments.

## Alternatives considered

- **Publish on every push to `main`.** Rejected: it makes a branch push a release and gives no
  human approval point.
- **Publish with a version tag only.** Rejected: a version tag is still a mutable name, and it says
  nothing about which commit produced the bytes.
- **Publish with `latest`.** Rejected: `latest` cannot be tied to a commit or audited.
- **A self-hosted runner or a deploy workflow over SSH.** Deferred: deploy access is an open IT
  decision, and publishing is independent of it.
- **A private registry with a dedicated service account.** Deferred until IT names a registry. The
  workflow variables make it a configuration change, not a redesign.
