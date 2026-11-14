# Release management — چهارسوق

How a commit becomes a running Production panel: how the images are built, how they are published,
how a release is selected, how it is promoted, and how it is rolled back.

Related: [ADR 015](../adr/015-container-image-release-and-publishing.md) ·
[Deployment](../architecture/deployment.md) ·
[Production runbook](production-runbook.md) ·
[Infrastructure readiness](infrastructure-readiness.md) ·
[IT requirements](it-requirements.md) ·
[Troubleshooting](troubleshooting.md)

Status: implemented in this repository. The workflow has **not** been executed against a real
release: no image has been pushed, no registry package exists, and no Production stack was started.

## 1. The release identity

| Concept            | Value                                                                 |
| ------------------ | --------------------------------------------------------------------- |
| Release identity   | The **Git commit SHA**. It is the only cross-environment identity.    |
| Image names        | `ghcr.io/<owner>/charsooq-api` and `ghcr.io/<owner>/charsooq-web`     |
| Image tags         | `<version>` (the release tag without its leading `v`) and `sha-<sha>` |
| Deployment pointer | The image **digest**: `ghcr.io/<owner>/charsooq-api@sha256:<digest>`  |
| Moving tags        | None. `latest` is never used, and neither is a `production` tag.      |
| Release tag format | `v<version>`, for example `v1.4.0`. The `v` is required.              |

The commit SHA is the identity because Staging (Vercel / FastAPI Cloud) and Production (Docker
Compose) build through different systems. The two environments never share a digest; they share a
commit. That mapping is recorded in the release record.

### 1.1 Version tag, SHA tag, and digest

These three names are often called "the same image". They are not, and the difference decides what
is authoritative.

| Name            | Example                                     | What it is                                     | Mutable?                                  |
| --------------- | ------------------------------------------- | ---------------------------------------------- | ----------------------------------------- |
| **Version tag** | `ghcr.io/<owner>/charsooq-api:1.4.0`        | A name the release workflow gives to one build | Yes — a registry accepts a re-push        |
| **SHA tag**     | `ghcr.io/<owner>/charsooq-api:sha-9f2c1d…`  | A name for the commit the image was built from | Yes — same as above                       |
| **Digest**      | `ghcr.io/<owner>/charsooq-api@sha256:82jf…` | The hash of the published manifest — the bytes | **No** — the content address of the image |

- A **tag is a pointer**, not a content address. `docker pull repo:1.4.0` resolves the name to
  whatever digest the registry holds _at that moment_.
- A **digest is the content address** of the published manifest. `repo@sha256:…` resolves to exactly
  those bytes, forever, as long as the registry keeps them.
- GitHub Container Registry has **no immutable-tag setting**: nothing in its documented feature set
  stops a second push from moving `:1.4.0` to a different digest. The workflow therefore _checks_
  that the tag does not exist before it pushes, but it cannot make the tag immutable.
- Therefore: **the digest is the only authoritative reference**, and it is the only reference
  Production is allowed to use. The tags exist for humans, for tracing, and for the release report.

The consequence is stated plainly in [ADR 015](../adr/015-container-image-release-and-publishing.md):
a tag is _written once by this workflow_, not _immutable by the registry_.

## 2. How a release is published

### 2.1 Trigger

The publish workflow is [`.github/workflows/release.yml`](../../.github/workflows/release.yml). It
runs on a **published GitHub Release** (`release: published`). There is no `push` trigger: a push to
`main` is never a Production release.

A manual run (`workflow_dispatch`) is possible, but it must name an existing published,
non-prerelease release. The release event is the authorization; the button is not. A manual run
executes the workflow file from the ref selected in the runner UI (by default `main`), while the
code it builds and checks is always the release tag.

Publishing a prerelease also starts the workflow — GitHub has no "published but not prerelease"
event — and the run then stops at step 1. That is a fail-closed result, not a published image.

### 2.2 What the workflow does, in order

1. **Resolve the release.** A draft or prerelease is rejected, and the release the API returns must
   be the one that was asked for. The release tag must be `v<version>`: the leading `v` is stripped
   to form the image tag, and requiring it keeps the release tag and the image tag in a one-to-one
   relation, so two different release tags can never name the same image tag. The check matches the
   whole string, so an embedded newline cannot slip through.
2. **Check out the release tag**, with the full history so an annotated tag can be peeled to its
   commit. The checked-out commit is compared with the tag's commit and the run stops if they differ.
3. **Resolve the build metadata**: the full commit SHA, the source repository URL, the build date,
   and the two image references (`ghcr.io/<lowercased-owner>/charsooq-api` and `…/charsooq-web`).
4. **Log in to the registry** with `GITHUB_TOKEN`. No new secret is created for publishing.
5. **Refuse to overwrite an existing release tag.** If the version tag or the SHA tag of either
   image already exists, the run stops before anything is pushed. If the registry state cannot be
   read at all, the run stops as well: an unknown state is not an absent tag. The version tag is
   the release identity and the SHA tag is the commit alias, and each is written once.
6. **Run the repository checks** (`ci.yml` is reusable, and the release job waits for it): frontend
   lint/format/typecheck/tests, backend checks on PostgreSQL, migration idempotency/drift/round-trip,
   the OpenAPI freshness check, the production build, and the Playwright e2e suite. The reusable
   workflow receives the release tag, so the checks run against **the release commit** and not
   against `main`.
7. **Build and push both images** from that one checkout, each with the two tags, the OCI
   metadata, a SLSA provenance attestation, and an SPDX SBOM.
8. **Attest build provenance** for both image digests, so `gh attestation verify` can check them.
9. **Verify the published images.** The revision label is read back from the registry and must equal
   the release commit. The published index must carry an attestation manifest.
10. **Record the digests** in the release body, in the run summary, and in a `release-images.json`
    artifact.

#### Concurrency and the remaining race

The workflow has a `concurrency` group per release tag and never cancels a running release, so two
runs of the _same_ release are serialized: the second waits for the first.

Two _different_ releases run in parallel. That is safe, because they publish different version
tags. It is only safe because the release tag must be `v<version>`: `v1.0.0` and `1.0.0` would map
to the same image tag while belonging to two different concurrency groups.

What the concurrency group does **not** cover is the window between step 5 (the tag does not exist)
and step 7 (the push). The registry does not enforce immutability, so a push from anywhere else
inside that window could move the tag. The window is seconds wide and needs registry write access,
but it is not closed. Only a registry that supports immutable tags closes it; GitHub Container
Registry does not, and IT has not named another registry yet.

### 2.3 Tags

For the release `v1.4.0` built from commit `9f2c…`:

| Reference                                      | Meaning                                  |
| ---------------------------------------------- | ---------------------------------------- |
| `ghcr.io/<owner>/charsooq-api:1.4.0`           | The release version                      |
| `ghcr.io/<owner>/charsooq-api:sha-9f2c1d…`     | The exact commit                         |
| `ghcr.io/<owner>/charsooq-api@sha256:<digest>` | The exact bytes — the deployment pointer |

Both tags point at the same digest when the release is published. The workflow refuses to publish
either of them a second time, so within this repository a tag is written once — but the registry
does not enforce that, and the tags are not immutable in the registry sense (see
[section 1.1](#11-version-tag-sha-tag-and-digest)). Use the **digest** in Production; the tags
exist for humans and for tracing.

### 2.4 OCI metadata

Every published image carries:

| Label                                  | Value                               |
| -------------------------------------- | ----------------------------------- |
| `org.opencontainers.image.revision`    | The full commit SHA                 |
| `org.opencontainers.image.version`     | The release version                 |
| `org.opencontainers.image.created`     | The build timestamp (UTC, RFC 3339) |
| `org.opencontainers.image.source`      | The repository URL                  |
| `org.opencontainers.image.title`       | `charsooq-api` / `charsooq-web`     |
| `org.opencontainers.image.description` | What the image is                   |
| `org.opencontainers.image.vendor`      | `ChaharSooq`                        |
| `org.opencontainers.image.licenses`    | `MIT`                               |

The `revision` label is the link from a deployed image back to a commit. It is also what the
workflow reads back from the registry to prove the link.

## 3. How a release is selected and promoted

### 3.1 Selecting the images

The release body carries both digests. Copy them into the deployment environment:

```bash
export CHARSOOQ_API_IMAGE='ghcr.io/<owner>/charsooq-api@sha256:<api-digest>'
export CHARSOOQ_WEB_IMAGE='ghcr.io/<owner>/charsooq-web@sha256:<web-digest>'
```

Both variables are **required** by `compose.production.yml` and have no default. An unset reference
fails the stack immediately:

```text
error while interpolating services.api.image: required variable CHARSOOQ_API_IMAGE is missing a value
```

That is deliberate: the previous defaults (`charsooq-api:production` / `charsooq-web:production`)
were moving local tags, and an unset variable used to deploy whatever happened to be in the local
image cache.

The two references must come from the **same release**. The API and the web image are built from one
checkout by one workflow run, so their `sha-…` tags are identical; if the two SHA tags differ, the
pair is wrong.

### 3.2 Verifying the selection

```bash
# The digests of what is actually in the local cache.
docker image inspect "$CHARSOOQ_API_IMAGE" --format '{{index .RepoDigests 0}}'
docker image inspect "$CHARSOOQ_WEB_IMAGE" --format '{{index .RepoDigests 0}}'

# The commit each image was built from.
make prod-image-revision
```

The second command prints the `org.opencontainers.image.revision` label of both images. It must
equal the approved commit SHA.

### 3.3 Promotion

```text
commit → CI → GitHub Release → images published → Staging exercised → approval → Production by digest
```

Staging runs on Vercel and FastAPI Cloud and does not consume these images. The commit SHA is what
is exercised there and what is approved; Production then deploys the images built from that same
commit. The full promotion procedure is in the
[Production runbook](production-runbook.md#6-update-and-release-workflow).

### 3.4 Rollback

A rollback is a promotion of the previous release's digests. Nothing is rebuilt:

```bash
export CHARSOOQ_API_IMAGE='ghcr.io/<owner>/charsooq-api@sha256:<previous-api-digest>'
export CHARSOOQ_WEB_IMAGE='ghcr.io/<owner>/charsooq-web@sha256:<previous-web-digest>'
docker compose -f compose.production.yml pull api web
docker compose -f compose.production.yml up -d --no-build --no-deps api web
```

The previous digests come from the previous release's body. A code rollback is **not** a database
rollback: an incompatible schema change needs a restore, not `alembic downgrade`. See
[backup-and-recovery.md](backup-and-recovery.md).

## 4. Building without a registry (the recorded fallback)

`make prod-build` builds both images from the current checkout. It is the fallback for a host with
no registry access, not the release path.

```bash
make prod-build
# → charsooq-api:<short-sha> and charsooq-web:<short-sha>, stamped with the commit SHA
```

The local tags are derived from the commit, so a stale local build cannot masquerade as the current
one, and the OCI metadata is filled in from the checkout just as it is for a published image. To run
them:

```bash
export CHARSOOQ_API_IMAGE='charsooq-api:<short-sha>'
export CHARSOOQ_WEB_IMAGE='charsooq-web:<short-sha>'
docker compose -f compose.production.yml up -d --no-build
```

This path has no SBOM, no provenance attestation, and no digest recorded in a release. Record the
image IDs and the commit SHA by hand. It is acceptable for the first rehearsal; it is not a release.

## 5. Provenance and SBOM

There are **two separate attestation mechanisms**, and they are stored in two different places. Both
are configured, and neither has been exercised against a real published image yet.

| Artifact                   | Produced by                             | Stored where                                         | Checked with                                                   |
| -------------------------- | --------------------------------------- | ---------------------------------------------------- | -------------------------------------------------------------- |
| BuildKit provenance + SBOM | `provenance: mode=max` and `sbom: true` | Inside the published index, as attestation manifests | `docker buildx imagetools inspect <image>@<digest>`            |
| GitHub build provenance    | `actions/attest-build-provenance`       | The GitHub attestation store, and the registry       | `gh attestation verify <image>@<digest> --repo <owner>/<repo>` |

- The **BuildKit** attestations travel _inside_ the image index. Every platform in the index gets a
  provenance attestation and an SBOM, so they are fetched by digest with the image and need no
  GitHub-specific tooling.
- The **GitHub** attestation is a Sigstore-signed statement about the published index digest. It is
  what `gh attestation verify` checks, and it is what a third party can verify without access to
  this repository's workflow runs.

```bash
# The in-index attestations (provenance and SBOM).
docker buildx imagetools inspect ghcr.io/<owner>/charsooq-api@sha256:<digest>

# The GitHub-signed provenance of the same digest.
gh attestation verify ghcr.io/<owner>/charsooq-api@sha256:<digest> \
  --repo <owner>/<repo>
```

The workflow fails the release when the published index carries no attestation manifest, and it
fails when the `revision` label read back from the registry is not the release commit. **Neither
check has run yet**, because no image has ever been published.

The provenance statement contains the source repository and the source commit, because the build
runs from the checked-out release tag with `SOURCE` and `VCS_REF` passed as build arguments. The
`revision` OCI label on the image carries the same commit SHA and is the field the workflow reads
back.

### 5.1 Pinned tool versions

Every action is pinned to a full commit SHA, so a moved action tag cannot change what a release
builds. The version behind each pin is written next to it in the workflow file.

| Action                            | Version | Commit                                     |
| --------------------------------- | ------- | ------------------------------------------ |
| `actions/checkout`                | v5.1.0  | `fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09` |
| `actions/setup-node`              | v4.4.0  | `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| `actions/setup-python`            | v5.6.0  | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| `actions/upload-artifact`         | v4.6.2  | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `actions/attest-build-provenance` | v4.2.2  | `4d101475d8b20a2381f78447822ac1eab6504dd8` |
| `docker/login-action`             | v4.8.0  | `8aa5831fb8d48d8f76594c7ddde61ae58019f550` |
| `docker/build-push-action`        | v7.4.0  | `c3c9e263c25d99ce0380d002d59b67737d91b0dc` |
| `pnpm/action-setup`               | v4.3.0  | `b906affcce14559ad1aafd4ab0e942779e9f58b1` |
| `astral-sh/setup-uv`              | v7.6.0  | `37802adc94f370d6bfd71619e3f0bf239e1f3b78` |

The registry, the two image names, and the internal API address are workflow-level constants in
`release.yml`, not repository variables: no repository setting has to exist for the workflow to run.

## 6. Operational rules

- **Never deploy a tag.** Deploy `repository@sha256:<digest>`.
- **Never rebuild on the Production host.** `prod-up` uses `--no-build`; the images come from the
  registry.
- **Never reuse a digest across releases.** Each release produces new digests.
- **Never delete or overwrite a release tag.** The workflow refuses to; a registry administrator
  must not either, because the registry itself will not stop them.
- **A release tag is `v<version>`.** The image tag is the version without the `v`.
- **One release, both images.** If only one image could be published, the release is incomplete and
  must not be promoted.
- **The release body is the release record.** Commit SHA, both digests, and the operator's approval
  belong there.

### 6.1 A failed publish

The guard refuses to publish over an existing tag, so a **re-run** of a release that already pushed
one of its images fails instead of overwriting it. That is deliberate, but it means a half-finished
publish cannot simply be retried: a registry administrator has to delete the half-published tag
first, and the release must then be published under a new version.

The cheapest recovery is therefore to publish a **new version** rather than to repair the old one.

## 7. What still needs an answer

| #   | Question                                                                    | Needed by                   | Consequence if unanswered                                                       |
| --- | --------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------- |
| 1   | Is GitHub Container Registry acceptable for internal Production images?     | Before the first publish    | The workflow constants point at `ghcr.io`; another registry needs a credential. |
| 2   | Can the Production host pull from the registry (DNS, TLS trust, proxy)?     | Before the first deployment | The host-build fallback applies; it has no SBOM or provenance.                  |
| 3   | May the images be stored outside the organization (GitHub's registry)?      | Before the first publish    | A private registry is required; the workflow needs a new credential.            |
| 4   | Who may create a GitHub Release, and who approves the Production promotion? | Before the first publish    | The release event has no authorizer.                                            |
| 5   | What image retention and vulnerability-scanning policy applies?             | Later                       | Old digests stay pullable, which is required for rollback anyway.               |
| 6   | Must the tags be immutable at the registry level?                           | Before the first publish    | The workflow's check is a best effort, not a guarantee (section 1.1).           |

Questions 1, 2, and 3 are the registry part of the IT checklist (question 4.6).

## 8. Verification performed for this work

Every check below is offline. None of them published anything.

| Check                                                                         | Result                                                                |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `make prod-build` (both Dockerfiles, from this checkout)                      | Built; the OCI labels carry the commit SHA, version, date, source     |
| `docker image inspect` on both built images                                   | The `revision` label equals the commit that built them                |
| `make prod-config`                                                            | Structure valid with documentation values only                        |
| `docker compose config` with the image variables unset                        | Fails closed with a named error                                       |
| `docker compose config` with digest references                                | The API, `provision`, `migrate`, and web resolve to the same image    |
| Workflow YAML parsed; every `run:` script checked with `bash -n`              | No syntax error                                                       |
| The release-body update script executed against a stubbed `gh`, twice         | The body is written correctly and the update is idempotent            |
| The release tag validation executed under `bash` with valid and invalid tags  | Accepted and rejected tags behave as documented, newline included     |
| The publish guard executed under `bash` against a stubbed registry            | Refuses an existing tag, refuses an unknown state, passes a fresh one |
| `docker buildx imagetools inspect` on a public multi-platform image           | The attestation-manifest query and the `revision` query both work     |
| Backend test suite (`test_release_workflow.py`, `test_production_compose.py`) | All pass                                                              |

Deliberately **not** done: no release was published, no image was pushed, no registry package was
created, no Production Compose stack was started, and `market-linux` was never contacted.
