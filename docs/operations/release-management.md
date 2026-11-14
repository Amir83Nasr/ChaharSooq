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

The commit SHA is the identity because Staging (Vercel / FastAPI Cloud) and Production (Docker
Compose) build through different systems. The two environments never share a digest; they share a
commit. That mapping is recorded in the release record.

## 2. How a release is published

### 2.1 Trigger

The publish workflow is [`.github/workflows/release.yml`](../../.github/workflows/release.yml). It
runs on a **published GitHub Release** (`release: published`). There is no `push` trigger: a push to
`main` is never a Production release.

A manual run (`workflow_dispatch`) is possible, but it must name an existing published,
non-prerelease release. The release event is the authorization; the button is not.

### 2.2 What the workflow does, in order

1. **Resolve the release.** A draft or prerelease is rejected. The version tag is the release tag
   without its leading `v` and must be a legal Docker tag.
2. **Check out the release tag**, with the full history so an annotated tag can be peeled to its
   commit. The checked-out commit is compared with the tag's commit and the run stops if they differ.
3. **Resolve the build metadata**: the full commit SHA, the source repository URL, the build date,
   and the two image references (`ghcr.io/<lowercased-owner>/charsooq-api` and `…/charsooq-web`).
4. **Log in to the registry** with `GITHUB_TOKEN`. No new secret is created for publishing.
5. **Refuse to overwrite an existing version tag.** If either `<version>` tag already exists, the run
   stops before anything is pushed. A release tag is written once.
6. **Run the repository checks** (`ci.yml` is reusable, and the release job waits for it): frontend
   lint/format/typecheck/tests, backend checks on PostgreSQL, migration idempotency/drift/round-trip,
   the OpenAPI freshness check, the production build, and the Playwright e2e suite.
7. **Build and push both images** from that one checkout, each with the two immutable tags, the OCI
   metadata, a SLSA provenance attestation, and an SPDX SBOM.
8. **Attest build provenance** for both image digests, so `gh attestation verify` can check them.
9. **Verify the published images.** The revision label is read back from the registry and must equal
   the release commit. The published index must carry an attestation manifest.
10. **Record the digests** in the release body, in the run summary, and in a `release-images.json`
    artifact.

### 2.3 Tags

For the release `v1.4.0` built from commit `9f2c…`:

| Reference                                      | Meaning                                  |
| ---------------------------------------------- | ---------------------------------------- |
| `ghcr.io/<owner>/charsooq-api:1.4.0`           | The release version                      |
| `ghcr.io/<owner>/charsooq-api:sha-9f2c1d…`     | The exact commit                         |
| `ghcr.io/<owner>/charsooq-api@sha256:<digest>` | The exact bytes — the deployment pointer |

Both tags point at the same digest. The version tag is immutable: the workflow refuses to publish it
twice. Use the **digest** in Production; the tags exist for humans and for tracing.

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

| Artifact              | How it is produced                                                                     | How it is checked                                              |
| --------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| SLSA provenance       | `provenance: mode=max` in the build (BuildKit) plus `attest-build-provenance` (GitHub) | `gh attestation verify <image>@<digest> --repo <owner>/<repo>` |
| SPDX SBOM             | `sbom: true` in the build (BuildKit's syft scanner)                                    | `docker buildx imagetools inspect <image>@<digest>`            |
| Both, in the registry | Attached to the published image index as an attestation manifest                       | The workflow fails if no attestation manifest is present       |

The SBOM and the provenance attestation are inside the published index, so they travel with the
image and can be fetched by digest:

```bash
docker buildx imagetools inspect ghcr.io/<owner>/charsooq-api@sha256:<digest>
```

## 6. Operational rules

- **Never deploy a tag.** Deploy `repository@sha256:<digest>`.
- **Never rebuild on the Production host.** `prod-up` uses `--no-build`; the images come from the
  registry.
- **Never reuse a digest across releases.** Each release produces new digests.
- **Never delete or overwrite a version tag.** The workflow refuses to; a registry administrator
  must not either.
- **One release, both images.** If only one image could be published, the release is incomplete and
  must not be promoted.
- **The release body is the release record.** Commit SHA, both digests, and the operator's approval
  belong there.

## 7. What still needs an answer

| #   | Question                                                                    | Needed by                   | Consequence if unanswered                                                       |
| --- | --------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------- |
| 1   | Is GitHub Container Registry acceptable for internal Production images?     | Before the first publish    | The workflow variables point at `ghcr.io`; another registry needs a credential. |
| 2   | Can the Production host pull from the registry (DNS, TLS trust, proxy)?     | Before the first deployment | The host-build fallback applies; it has no SBOM or provenance.                  |
| 3   | May the images be stored outside the organization (GitHub's registry)?      | Before the first publish    | A private registry is required; the workflow needs a new credential.            |
| 4   | Who may create a GitHub Release, and who approves the Production promotion? | Before the first publish    | The release event has no authorizer.                                            |
| 5   | What image retention and vulnerability-scanning policy applies?             | Later                       | Old digests stay pullable, which is required for rollback anyway.               |

Questions 1, 2, and 3 are the registry part of the IT checklist (question 4.6).

## 8. Verification performed for this work

| Check                                                                         | Result                                                             |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `make prod-build` (both Dockerfiles, from this checkout)                      | Built; the OCI labels carry the commit SHA, version, date, source  |
| `docker image inspect` on both built images                                   | The `revision` label equals the commit that built them             |
| `make prod-config`                                                            | Structure valid with documentation values only                     |
| `docker compose config` with the image variables unset                        | Fails closed with a named error                                    |
| `docker compose config` with digest references                                | The API, `provision`, `migrate`, and web resolve to the same image |
| Workflow YAML parsed; every `run:` script checked with `bash -n`              | No syntax error                                                    |
| The release-body update script executed against a stubbed `gh`, twice         | The body is written correctly and the update is idempotent         |
| Backend test suite (`test_release_workflow.py`, `test_production_compose.py`) | All pass                                                           |

Deliberately **not** done: no release was published, no image was pushed, no registry package was
created, no Production Compose stack was started, and `market-linux` was never contacted.
