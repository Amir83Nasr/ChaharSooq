# ADR 019 — Publish the Release after the images are verified

Date: 2026-11-18 · Status: accepted

## Context

[ADR 015](015-container-image-release-and-publishing.md) made a published GitHub Release the trigger
for image publication. To break that cycle, the tag-push workflow
(`.github/workflows/create-release.yml`) published the Release immediately with placeholder image
references ("Pending image publication"), and the image workflow patched the body afterwards. The
public Release therefore existed — and announced artifacts — before those artifacts existed. A
failed build, attestation, or verification step left a public Release whose body either promised
images that were never published or still said "Pending"; operators had no all-or-nothing signal.

The digest table only needs values produced by the build, so a correct body cannot be written before
the build finishes. This changes the order of the two events, not the deployment contract: ADR 018
still deploys by digest from the `latest` discovery pointer.

## Decision

- **A version tag is the release request, and the Release is published last.** A push of a `v*`
  tag, or a manual `workflow_dispatch` with an existing tag, runs the single
  [`.github/workflows/release.yml`](../../.github/workflows/release.yml) pipeline: validate the tag,
  run the reusable CI suite against that exact commit, build and push both images, attest and verify
  them, then create the GitHub Release with its final body. `create-release.yml` is removed.
- **No placeholder or premature publication.** The Release body is generated only after both image
  digests exist and the published images have been read back from the registry. It contains the
  final digest table, commit SHA, and release notes. Nothing in a published Release says
  "Pending"; if CI, the build, or verification fails, no Release is published at all.
- **An interrupted run may leave a draft.** If a previous run created a draft, a retry reuses that
  draft and publishes it with the final body. An already published Release is never overwritten;
  a new version tag is required. `workflow_dispatch` is an alternate entry point for the same
  pipeline, not a second authorization to republish an existing Release.
- **A push to a branch is still never a release.** The trigger is `push` on `v*` tags only; a push to
  `main` continues to run CI without publishing images or a Release. Publishes stay serialized so
  the `latest` image pointer names the newest completed release.
- **Everything else in ADR 015 and ADR 018 is unchanged.** The strict `vMAJOR.MINOR.PATCH` tag,
  GHCR, the version and `sha-<commit>` write-once tags, OCI metadata, provenance and SBOM, the
  digest as deployment identity, and the operator-run single-slot deploy all remain in force.
  Only the trigger/ordering clause of ADR 015 is superseded.

## Consequences

- A published Release is a trustworthy signal: by the time it appears, both images exist, carry the
  right revision label, have attestations, and have verified digests recorded in its body.
- A failed release leaves no published Release. It can leave pushed image tags and a moved `latest`
  pointer from a partially completed publish; as in ADR 015, the tag guard refuses to retry over
  those tags, so the operator must use a new version or have the registry tags removed. Deploying
  by explicit digest avoids ambiguity during that window.
- The GitHub Release is a single final write, so its notes and digest table cannot disagree.
- Manual dispatch now names a tag to release rather than an already published Release; any existing
  automation that passed a published Release tag to `workflow_dispatch` must be updated.

## Alternatives considered

- **Keep publishing on tag push and patch the body later.** Rejected: it is the current failure
  mode — a public Release can announce images that do not exist.
- **Create a draft on tag push and have a second workflow publish it.** Rejected: two workflows
  would have to pass the tag, digest outputs, and release state through artifacts or polling. One
  workflow with a native job dependency is simpler and cannot half-run.
- **Publish the images from `release: published` and wait in the release workflow.** Rejected:
  the two triggers would depend on each other and deadlock until a timeout.
