"""Release workflow contract — one release, two images, immutable and traceable.

The workflow file is parsed, not executed: no registry, no network, and no
credential is involved. The assertions describe the properties a published
image must have, so a change that weakens them fails the build.

The two shell blocks that decide whether an image may be published at all —
the release tag validation and the "the tag does not exist yet" guard — are
additionally executed under `bash` with stubbed binaries. No credential, no
registry, and no network is involved in those either.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
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

# A pinned action: the owner/repository and a full 40-character commit SHA.
# A moving `@v4` tag is not acceptable for a workflow that pushes images.
PINNED_ACTION = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")

# The two shell blocks are executed with the system bash, never through a shell.
BASH = shutil.which("bash") or "/bin/bash"


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


def _release_job() -> dict[str, Any]:
    return cast(dict[str, Any], _workflow()["jobs"]["release"])


def _steps() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], _release_job()["steps"])


def _step(step_id: str) -> dict[str, Any]:
    for step in _steps():
        if step.get("id") == step_id:
            return step
    raise AssertionError(f"no release step with id {step_id}")


def _script(step_id: str) -> str:
    return str(_step(step_id)["run"])


def _compose() -> dict[str, Any]:
    with COMPOSE_PATH.open(encoding="utf-8") as handle:
        return cast(dict[str, Any], yaml.safe_load(handle))


def _ci_workflow() -> dict[str, Any]:
    with CI_WORKFLOW_PATH.open(encoding="utf-8") as handle:
        return cast(dict[str, Any], yaml.safe_load(handle))


def _ci_triggers() -> dict[str, Any]:
    workflow = _ci_workflow()
    # PyYAML reads the `on` key as the boolean True.
    triggers = workflow.get("on")
    if triggers is None:
        triggers = workflow.get(True)  # type: ignore[arg-type]
    return cast(dict[str, Any], triggers)


def _used_actions(workflow: dict[str, Any]) -> list[str]:
    """Every `uses:` value in a workflow, including the ones inside jobs."""

    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in cast(dict[object, object], node).items():
                if key == "uses" and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in cast(list[object], node):
                walk(item)

    walk(workflow)
    return found


def _tag_validation_block() -> str:
    """The shell block that turns a release tag into an image tag."""

    lines = _script("validate").splitlines()
    start = next(i for i, line in enumerate(lines) if 'if ! [[ "$TAG" =~' in line)
    end = next(
        i
        for i, line in enumerate(lines[start:], start)
        if line.strip().startswith('echo "version=')
    )
    return "\n".join(lines[start : end + 1])


def _run_guard(
    tmp_path: Path,
    existing: tuple[str, ...],
    unknown: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run the guard step with a stubbed `docker`.

    The stub reports the references in `existing` as present and every other
    reference as absent. With `unknown` it reports an error that is not a
    "not found", which is what an unreachable or unauthorized registry looks
    like.
    """

    stub_dir = tmp_path / "bin"
    stub_dir.mkdir(parents=True, exist_ok=True)
    stub = stub_dir / "docker"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'ref="${@: -1}"\n'
        'case "$ref" in\n'
        + "".join(f'  "{ref}") echo "Name: $ref"; exit 0 ;;\n' for ref in existing)
        + (
            '  *) echo "ERROR: $ref: denied" >&2; exit 1 ;;\n'
            if unknown
            else '  *) echo "ERROR: $ref: not found" >&2; exit 1 ;;\n'
        )
        + "esac\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)

    env = {
        "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
        "API_IMAGE": "ghcr.io/ns/charsooq-api",
        "WEB_IMAGE": "ghcr.io/ns/charsooq-web",
        "VERSION": "1.0.0",
        "SHA": "1" * 40,
    }
    return subprocess.run(  # noqa: S603 - fixed interpreter, no shell
        [BASH, "-c", _script("guard")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _run_publish_release(
    tmp_path: Path,
    *,
    api_status: int,
    api_body: str,
    draft_id: str = "",
) -> subprocess.CompletedProcess[str]:
    """Run the publication step with a stubbed `gh`.

    The stub returns `api_body` with `api_status` for `gh api` and prints every
    other `gh` call, so the test can see which release command was issued
    without a token, a network, or a real release.
    """

    stub_dir = tmp_path / "bin"
    stub_dir.mkdir(parents=True, exist_ok=True)
    stub = stub_dir / "gh"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "api" ]; then\n'
        '  printf "%s" "$STUB_API_BODY"\n'
        '  exit "$STUB_API_STATUS"\n'
        "fi\n"
        'printf "gh %s\\n" "$*"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    notes = tmp_path / "notes.md"
    notes.write_text("release notes\n", encoding="utf-8")

    env = {
        "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
        "TAG": "v1.0.0",
        "GITHUB_REPOSITORY": "ns/charsooq",
        "GH_TOKEN": "stub",
        "BODY_FILE": str(notes),
        "DRAFT_ID": draft_id,
        "SHA": "1" * 40,
        "STUB_API_BODY": api_body,
        "STUB_API_STATUS": str(api_status),
    }
    return subprocess.run(  # noqa: S603 - fixed interpreter, no shell
        [BASH, "-c", _script("publish_release")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


API_NOT_FOUND = '{"message":"Not Found","status":"404"}'
API_PUBLISHED = '{"tag_name":"v1.0.0","draft":false}'
API_DRAFT = '{"tag_name":"v1.0.0","draft":true}'
API_SERVER_ERROR = '{"message":"Internal Server Error","status":"500"}'


def test_a_version_tag_requests_a_release_and_publication_is_last() -> None:
    triggers = _triggers()

    # A push to `main` is never a Production release; only a version tag asks
    # for one. The Release is created after the images are verified, so the
    # old `release: published` trigger would now be circular.
    assert triggers["push"] == {"tags": ["v*"]}
    assert "release" not in triggers
    assert "branches" not in triggers["push"]
    assert "pull_request" not in triggers
    # A manual run names the tag to release, not an existing Release.
    assert triggers["workflow_dispatch"]["inputs"]["tag"]["required"] is True
    steps = [str(step.get("name")) for step in _steps()]
    assert steps.index("Verify the published images") < steps.index("Publish the GitHub Release")
    assert "Pending" not in WORKFLOW_PATH.read_text(encoding="utf-8")


def test_the_release_job_runs_the_repository_checks_first() -> None:
    workflow = _workflow()

    # ci.yml is reusable, and the release job waits for it: no image is
    # published from a commit that did not pass the checks.
    assert workflow["jobs"]["verify"]["uses"] == "./.github/workflows/ci.yml"
    assert _release_job()["needs"] == ["verify"]


def test_permissions_are_the_minimum_the_release_needs() -> None:
    permissions = _release_job()["permissions"]

    assert permissions == {
        "contents": "write",  # publish the Release with the final digests
        "pull-requests": "read",  # PR titles in the release notes
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

    assert checkout["with"]["ref"] == "${{ env.TAG }}"
    # The full history is needed to peel an annotated tag to its commit.
    assert checkout["with"]["fetch-depth"] == 0
    # The token is not left in the checkout configuration.
    assert checkout["with"]["persist-credentials"] is False


def test_an_existing_published_release_is_never_overwritten() -> None:
    script = _script("release")

    # A retry may reuse an interrupted draft, but a public Release is final.
    assert "releases/tags/" in script
    assert ".draft" in script
    assert "already published" in script
    assert "exit 1" in script
    # A strict semver tag is required; validation runs in the `validate` step.
    assert "=~ ^v(" in _script("validate")


def test_publish_creates_a_release_when_none_exists_yet(tmp_path: Path) -> None:
    """A 404 prints an error JSON on stdout; it is not a published release."""

    result = _run_publish_release(tmp_path, api_status=1, api_body=API_NOT_FOUND)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "gh release create v1.0.0" in result.stdout
    assert "concurrently" not in result.stdout


def test_publish_still_refuses_a_concurrently_published_release(tmp_path: Path) -> None:
    result = _run_publish_release(tmp_path, api_status=0, api_body=API_PUBLISHED)

    assert result.returncode != 0
    assert "published concurrently" in result.stdout
    assert "gh release create" not in result.stdout


def test_publish_reuses_a_draft_left_by_an_interrupted_run(tmp_path: Path) -> None:
    result = _run_publish_release(tmp_path, api_status=0, api_body=API_DRAFT, draft_id="123")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "gh release edit v1.0.0" in result.stdout


@pytest.mark.parametrize(
    ("status", "body"),
    [(1, API_SERVER_ERROR), (1, ""), (1, "not json")],
)
def test_publish_fails_closed_on_an_unknown_release_state(
    tmp_path: Path, status: int, body: str
) -> None:
    result = _run_publish_release(tmp_path, api_status=status, api_body=body)

    assert result.returncode != 0
    assert "could not determine release state" in result.stdout
    assert "gh release" not in result.stdout


def test_the_release_tag_is_validated_as_a_whole_string() -> None:
    """A tag must be `v<version>`, and an embedded newline must not pass.

    The check is executed under bash, because a regular expression that
    matches line by line would accept `v1.0.0` followed by a newline.
    """

    block = _tag_validation_block()

    def version_for(tag: str) -> str | None:
        result = subprocess.run(  # noqa: S603 - fixed interpreter, no shell
            [
                BASH,
                "-c",
                'set -euo pipefail\nexport TAG="$1" GITHUB_OUTPUT=/dev/null\n'
                + block
                + '\nprintf "%s" "$version"',
                "bash",
                tag,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout

    assert version_for("v1.0.0") == "1.0.0"
    assert version_for("v0.1.0") == "0.1.0"
    # A release tag is exactly vMAJOR.MINOR.PATCH (ADR 019).
    assert version_for("v1.0.0-rc.1") is None
    # Without the `v` the tag would collide with another tag's image tag.
    assert version_for("1.0.0") is None
    assert version_for("v") is None
    assert version_for("v-1.0") is None
    assert version_for("v1.0.0 with spaces") is None
    # A newline must not smuggle a second line past the check.
    assert version_for("v1.0.0\nEVIL=1") is None


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
        assert "VERSION=${{ steps.validate.outputs.version }}" in args
        assert "SOURCE=${{ steps.meta.outputs.source }}" in args
        assert "BUILD_DATE=${{ steps.meta.outputs.build_date }}" in args


def test_image_tags_carry_the_version_the_commit_and_a_discovery_pointer() -> None:
    for step_id in ("build_api", "build_web"):
        tags = [
            line.strip()
            for line in str(_step(step_id)["with"]["tags"]).splitlines()
            if line.strip()
        ]
        assert len(tags) == 3
        assert tags[0].endswith(":${{ steps.validate.outputs.version }}")
        assert tags[1].endswith(":sha-${{ steps.meta.outputs.sha }}")
        assert tags[2].endswith(":latest")

    # `latest` is only a name the server resolves to a digest before deploying;
    # the version and SHA tags remain the immutable release identity.
    assert "discovery pointer" in WORKFLOW_PATH.read_text(encoding="utf-8")


def test_publishes_are_serialized_so_latest_names_the_newest_release() -> None:
    concurrency = _workflow()["concurrency"]

    assert concurrency == {"group": "release", "cancel-in-progress": False}


def test_the_verify_step_checks_the_latest_pointer() -> None:
    script = _script("verify_images")

    assert '"${image}:latest"' in script
    assert "{{.Manifest.Digest}}" in script
    assert "does not match" in script


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
    assert "already exist" in script
    assert "exit 1" in script
    # Both published names are guarded: the version tag and the commit alias.
    assert "${API_IMAGE}:${VERSION}" in script
    assert "${API_IMAGE}:sha-${SHA}" in script
    assert "${WEB_IMAGE}:sha-${SHA}" in script


def test_the_guard_refuses_to_publish_over_an_existing_tag(tmp_path: Path) -> None:
    result = _run_guard(tmp_path=tmp_path, existing=("ghcr.io/ns/charsooq-api:1.0.0",))

    assert result.returncode != 0
    assert "already exist" in result.stdout


def test_the_guard_fails_closed_on_an_unknown_registry_state(tmp_path: Path) -> None:
    """An unreadable registry is not an absent tag."""

    result = _run_guard(tmp_path=tmp_path, existing=(), unknown=True)

    assert result.returncode != 0
    assert "refusing to publish" in result.stdout


def test_the_guard_lets_a_fresh_release_through(tmp_path: Path) -> None:
    result = _run_guard(tmp_path=tmp_path, existing=())

    assert result.returncode == 0, result.stdout + result.stderr


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
    script = _script("verify_images")

    # The commit link is verified against the published bytes, not assumed.
    assert "imagetools inspect" in script
    assert "org.opencontainers.image.revision" in script
    assert 'if [ "$revisions" != "$SHA" ]; then' in script
    assert "exit 1" in script


def test_the_digests_are_recorded_in_the_release_report() -> None:
    record = _script("record")
    release = _script("release_body")
    publish = _script("publish_release")

    assert "release-images.json" in record
    assert "$GITHUB_STEP_SUMMARY" in record
    # The final body is built from the verified digests, then handed to the
    # publication step as a file. No placeholder is ever published.
    assert "charsooq:image-digests:start" in release
    assert "${API_DIGEST}" in release
    assert "${WEB_DIGEST}" in release
    assert "--notes-file" in publish
    assert "gh release create" in publish
    assert "gh release edit" in publish  # reuse a draft left by an interrupted run
    assert "published concurrently" in publish


def test_the_web_build_argument_matches_the_production_compose_file() -> None:
    compose = _compose()
    # The web rewrite target is baked into the image, so the single `web`
    # service must reach the API as `api`, exactly as the release builds it.
    compose_value = compose["services"]["web"]["build"]["args"]["API_URL_INTERNAL"]

    api_url_internal = cast(str, _release_job()["env"]["API_URL_INTERNAL"])
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


def test_the_normal_ci_triggers_are_preserved() -> None:
    """Making the CI reusable must not disable the ordinary CI."""

    triggers = _ci_triggers()

    assert triggers["push"]["branches"] == ["main"]
    assert "pull_request" in triggers
    # The reusable trigger is an addition, not a replacement.
    assert "workflow_call" in triggers


def test_the_release_verification_runs_against_the_release_commit() -> None:
    """The checks must run against the published commit, not against `main`."""

    verify = _workflow()["jobs"]["verify"]

    assert verify["uses"] == "./.github/workflows/ci.yml"
    # The release tag is handed to the reusable workflow.
    assert (
        verify["with"]["ref"]
        == "${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref_name }}"
    )
    # The reusable workflow takes it as an input and checks it out.
    ci_inputs = _ci_triggers()["workflow_call"]["inputs"]
    assert "ref" in ci_inputs
    assert ci_inputs["ref"]["required"] is False
    ci_checkouts = [
        step
        for job in _ci_workflow()["jobs"].values()
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout")
    ]
    assert ci_checkouts
    for checkout in ci_checkouts:
        # An empty input keeps the default behaviour of a push or a pull
        # request; the release workflow fills it in.
        assert checkout["with"]["ref"] == "${{ inputs.ref }}"


def test_the_ci_concurrency_group_separates_the_release_verification() -> None:
    """A release verification must not cancel the CI of `main`."""

    concurrency = _ci_workflow()["concurrency"]

    assert concurrency["group"] == "ci-${{ inputs.ref || github.ref }}"


def test_every_action_is_pinned_to_a_full_commit_sha() -> None:
    """A moving action tag is a supply-chain risk in a publishing workflow."""

    for name, workflow in (
        ("release.yml", _workflow()),
        ("ci.yml", _ci_workflow()),
    ):
        for uses in _used_actions(workflow):
            if uses.startswith("."):
                # A local reusable workflow, not an action.
                continue
            assert PINNED_ACTION.match(uses), f"{name}: {uses} is not pinned to a commit SHA"


# ─── Production deployment contract ──────────────────────────────────────────

DEPLOY_SCRIPT_PATH = REPO_ROOT / "deploy" / "scripts" / "deploy.sh"


def test_the_release_workflow_publishes_images_and_the_release_but_never_deploys() -> None:
    """Deployment is a manual, single command on the server — not a CI job."""

    workflow = _workflow()

    assert set(workflow["jobs"]) == {"verify", "release"}
    assert "deploy" not in workflow["jobs"]
    assert "pull_request" not in _triggers()
    assert "deploy" not in _triggers()["workflow_dispatch"]["inputs"]
    # No workflow may target the Production host; the server is not a runner.
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    for path in workflows_dir.glob("*.yml"):
        assert "charsooq-production" not in path.read_text(encoding="utf-8")
    for job in _ci_workflow()["jobs"].values():
        assert "self-hosted" not in str(job.get("runs-on", ""))


def test_the_release_is_published_only_after_the_images_are_verified() -> None:
    ids = [str(step.get("id")) for step in _steps()]

    assert ids.index("verify_images") < ids.index("notes") < ids.index("release_body")
    assert ids.index("release_body") < ids.index("publish_release")


def test_a_manual_run_names_a_tag_to_release() -> None:
    tag_input = _triggers()["workflow_dispatch"]["inputs"]["tag"]

    assert tag_input["required"] is True
    assert tag_input["type"] == "string"
    assert "tag" in tag_input["description"].lower()


def test_the_deploy_script_is_fail_closed_and_deploys_by_digest() -> None:
    script = DEPLOY_SCRIPT_PATH.read_text(encoding="utf-8")
    # Comments describe decisions; assertions apply to the executable lines.
    code = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))

    assert "set -euo pipefail" in code
    assert "set -x" not in code
    # Content addresses only; a tag is resolved to a digest before any change.
    assert "*@sha256:*" in code
    assert "docker buildx imagetools inspect" in code
    # Nothing is ever removed.
    assert "down -v" not in code
    assert "volume prune" not in code
    assert "system prune" not in code
    # No blue-green machinery remains.
    for removed in (
        "detect_active_slot",
        "write_upstream",
        "active-upstream.caddy",
        "ACTIVE_SLOT",
        "STATE_FILE",
        "--profile",
    ):
        assert removed not in code
    # Ordered one-shot steps, then the single api/web pair, then health.
    pull = code.index('"${COMPOSE[@]}" pull api web')
    provision = code.index('"${COMPOSE[@]}" run --rm provision')
    migrate = code.index('"${COMPOSE[@]}" run --rm migrate')
    up = code.index('"${COMPOSE[@]}" up -d --no-build --remove-orphans')
    probe = code.index("probe /api/v1/health")
    assert pull < provision < migrate < up < probe
    assert "probe /login" in code
    assert "USR1" in code  # refresh Caddy's upstream DNS after web is replaced
    # Non-secret deployment values come from the host, not from GitHub.
    assert "CHARSOOQ_ENV_FILE" in code
    assert "secrets." not in code
    assert "CHARSOOQ_EDGE_SUBNET" in code
    assert "CHARSOOQ_PUBLIC_SCHEME" in code
    assert "CHARSOOQ_PUBLIC_PORT" in code


def test_the_deploy_script_is_valid_bash() -> None:
    result = subprocess.run(  # noqa: S603 - fixed interpreter, no shell
        [BASH, "-n", str(DEPLOY_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
