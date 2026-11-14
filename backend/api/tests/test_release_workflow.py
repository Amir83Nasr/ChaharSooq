"""Release workflow contract — one release, two images, immutable and traceable.

The workflow file is parsed, not executed: no registry, no network, and no
credential is involved. The assertions describe the properties a published
image must have, so a change that weakens them fails the build.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"
COMPOSE_PATH = REPO_ROOT / "compose.production.yml"
DOCKERFILES = {
    "api": REPO_ROOT / "Dockerfile.api",
    "web": REPO_ROOT / "Dockerfile.web",
}

OCI_LABELS = (
    "org.opencontainers.image.revision",
    "org.opencontainers.image.version",
    "org.opencontainers.image.created",
    "org.opencontainers.image.source",
)


def _workflow() -> dict[str, Any]:
    with WORKFLOW_PATH.open(encoding="utf-8") as handle:
        return cast(dict[str, Any], yaml.safe_load(handle))


def _triggers() -> dict[str, Any]:
    workflow = _workflow()
    # PyYAML reads the `on` key as the boolean True.
    triggers = workflow.get("on")
    if triggers is None:
        triggers = workflow.get(True)  # type: ignore[arg-type]
    return cast(dict[str, Any], triggers)


def _publish_job() -> dict[str, Any]:
    return cast(dict[str, Any], _workflow()["jobs"]["publish"])


def _steps() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], _publish_job()["steps"])


def _step(step_id: str) -> dict[str, Any]:
    for step in _steps():
        if step.get("id") == step_id:
            return cast(dict[str, Any], step)
    raise AssertionError(f"no release step with id {step_id}")


def _script(step_id: str) -> str:
    return str(_step(step_id)["run"])


def _compose() -> dict[str, Any]:
    with COMPOSE_PATH.open(encoding="utf-8") as handle:
        return cast(dict[str, Any], yaml.safe_load(handle))


def test_publishing_is_bound_to_a_published_release() -> None:
    triggers = _triggers()

    # A push to `main` is never a Production release, so there is no push
    # trigger at all.
    assert "push" not in triggers
    assert triggers["release"]["types"] == ["published"]
    # A manual run must name an existing release, so it is an explicit and
    # controlled mechanism rather than a second, unchecked trigger.
    assert triggers["workflow_dispatch"]["inputs"]["tag"]["required"] is True


def test_the_publish_job_runs_the_repository_checks_first() -> None:
    workflow = _workflow()

    # ci.yml is reusable, and the release job waits for it: no image is
    # published from a commit that did not pass the checks.
    assert workflow["jobs"]["verify"]["uses"] == "./.github/workflows/ci.yml"
    assert _publish_job()["needs"] == ["verify"]


def test_permissions_are_the_minimum_the_publish_needs() -> None:
    permissions = _publish_job()["permissions"]

    assert permissions == {
        "contents": "write",  # record the digests in the release body
        "packages": "write",  # push to the container registry
        "id-token": "write",  # OIDC token for the attestation
        "attestations": "write",  # store the build provenance attestation
    }
    # The workflow default stays read-only, so the verify job cannot write.
    assert _workflow()["permissions"] == {"contents": "read"}


def test_publishing_uses_the_repository_token_and_no_new_secret() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    secrets_used = set(re.findall(r"secrets\.([A-Z_]+)", text))
    assert secrets_used == {"GITHUB_TOKEN"}


def test_the_release_commit_is_checked_out_by_tag() -> None:
    checkout = next(
        step for step in _steps() if str(step.get("uses", "")).startswith("actions/checkout")
    )

    assert checkout["with"]["ref"] == "${{ steps.release.outputs.tag }}"
    # The full history is needed to peel an annotated tag to its commit.
    assert checkout["with"]["fetch-depth"] == 0
    # The token is not left in the checkout configuration.
    assert checkout["with"]["persist-credentials"] is False


def test_the_release_must_be_a_stable_published_release() -> None:
    script = _script("release")

    assert "releases/tags/" in script  # a manual run resolves an existing release
    assert ".draft" in script
    assert ".prerelease" in script
    # The version tag is the release tag without its leading "v" and must be
    # a legal Docker tag.
    assert 'version="${tag#v}"' in script


def test_both_images_are_built_from_the_same_commit() -> None:
    api = _step("build_api")
    web = _step("build_web")

    assert api["with"]["file"] == "Dockerfile.api"
    assert web["with"]["file"] == "Dockerfile.web"
    assert api["with"]["context"] == web["with"]["context"] == "."
    # The commit is the same value in both builds, and it is the value the
    # checkout was verified against.
    for step in (api, web):
        args = str(step["with"]["build-args"])
        assert "VCS_REF=${{ steps.meta.outputs.sha }}" in args
        assert "VERSION=${{ steps.release.outputs.version }}" in args
        assert "SOURCE=${{ steps.meta.outputs.source }}" in args
        assert "BUILD_DATE=${{ steps.meta.outputs.build_date }}" in args


def test_image_tags_carry_the_version_and_the_commit_and_never_latest() -> None:
    for step_id in ("build_api", "build_web"):
        tags = [
            line.strip()
            for line in str(_step(step_id)["with"]["tags"]).splitlines()
            if line.strip()
        ]
        assert len(tags) == 2
        assert tags[0].endswith(":${{ steps.release.outputs.version }}")
        assert tags[1].endswith(":sha-${{ steps.meta.outputs.sha }}")
        assert not any(tag.endswith(":latest") for tag in tags)

    # The whole workflow must not publish a moving tag.
    assert ":latest" not in WORKFLOW_PATH.read_text(encoding="utf-8")


def test_the_image_names_follow_the_repository_layout() -> None:
    api = _step("build_api")
    web = _step("build_web")

    assert "steps.meta.outputs.api_image" in str(api["with"]["tags"])
    assert "steps.meta.outputs.web_image" in str(web["with"]["tags"])
    script = _script("meta")
    # ghcr.io/<owner>/<image>, with the owner lowercased for the registry.
    assert "${REGISTRY}/${namespace}/${API_IMAGE_NAME}" in script
    assert "tr '[:upper:]' '[:lower:]'" in script


def test_an_existing_release_tag_is_never_overwritten() -> None:
    script = _script("guard")

    assert "imagetools inspect" in script
    assert "already exists" in script
    assert "exit 1" in script


def test_provenance_and_sbom_travel_with_the_published_image() -> None:
    for step_id in ("build_api", "build_web"):
        step = _step(step_id)
        assert step["with"]["provenance"] == "mode=max"
        assert step["with"]["sbom"] is True

    attestations = [
        step for step in _steps() if "attest-build-provenance" in str(step.get("uses", ""))
    ]
    assert len(attestations) == 2
    for step in attestations:
        assert step["with"]["push-to-registry"] is True
        assert "subject-digest" in step["with"]


def test_the_published_image_is_read_back_from_the_registry() -> None:
    script = _script("verify")

    # The commit link is verified against the published bytes, not assumed.
    assert "imagetools inspect" in script
    assert "org.opencontainers.image.revision" in script
    assert 'if [ "$revisions" != "$SHA" ]; then' in script
    assert "exit 1" in script


def test_the_digests_are_recorded_in_the_release_report() -> None:
    record = _script("record")
    release = _script("release_body")

    assert "release-images.json" in record
    assert "$GITHUB_STEP_SUMMARY" in record
    # The release body carries the digests, so the artifact can be identified
    # later without reading the workflow log.
    assert "charsooq:image-digests:start" in release
    assert "--method" in release and "PATCH" in release


def test_the_web_build_argument_matches_the_production_compose_file() -> None:
    compose = _compose()
    compose_value = compose["services"]["web"]["build"]["args"]["API_URL_INTERNAL"]

    api_url_internal = cast(str, _publish_job()["env"]["API_URL_INTERNAL"])
    assert api_url_internal == compose_value
    assert "API_URL_INTERNAL=${{ env.API_URL_INTERNAL }}" in str(
        _step("build_web")["with"]["build-args"]
    )


def test_both_dockerfiles_carry_the_oci_release_labels() -> None:
    for name, path in DOCKERFILES.items():
        content = path.read_text(encoding="utf-8")
        for label in OCI_LABELS:
            assert "LABEL" in content
            assert label in content, f"{name} must declare {label}"
        # The label values come from build arguments the release workflow
        # passes, so an image cannot claim a commit it was not built from.
        for arg in ("VCS_REF", "BUILD_DATE", "VERSION", "SOURCE"):
            assert f"ARG {arg}=" in content
