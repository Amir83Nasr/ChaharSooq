"""Final CI/CD and Blue-Green validation contracts (offline, no Production contact).

This module complements ``test_release_workflow.py``, ``test_production_compose.py``,
and ``test_production_proxy.py`` with scenario- and security-focused assertions for
the event-driven release/deploy path. It parses workflow/compose/scripts/docs and
runs only local, side-effect-free checks (YAML parsing, string contracts, ``bash -n``).

No registry, GitHub API, Docker daemon, host, secret file, or Production stack is
contacted. No volume, database, image, or network setting is changed.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
RELEASE_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CREATE_RELEASE_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "create-release.yml"
COMPOSE_PATH = REPO_ROOT / "compose.production.yml"
DEPLOY_SCRIPT_PATH = REPO_ROOT / "deploy" / "scripts" / "deploy.sh"
PREFLIGHT_SCRIPT_PATH = REPO_ROOT / "deploy" / "runner" / "preflight.sh"
ACTIVE_UPSTREAM_PATH = REPO_ROOT / "deploy" / "caddy" / "active-upstream.caddy"
SITE_CADDY_PATH = REPO_ROOT / "deploy" / "caddy" / "site.caddy"

BASH = shutil.which("bash") or "/bin/bash"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return cast(dict[str, Any], yaml.safe_load(handle))


def _release_workflow() -> dict[str, Any]:
    return _load_yaml(RELEASE_WORKFLOW_PATH)


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    triggers = workflow.get("on")
    if triggers is None:
        triggers = workflow.get(True)  # type: ignore[arg-type]  # PyYAML reads `on` as True
    return cast(dict[str, Any], triggers)


def _publish_job() -> dict[str, Any]:
    return cast(dict[str, Any], _release_workflow()["jobs"]["publish"])


def _deploy_job() -> dict[str, Any]:
    return cast(dict[str, Any], _release_workflow()["jobs"]["deploy"])


def _script(step_id: str, job: dict[str, Any] | None = None) -> str:
    job = job or _publish_job()
    for step in cast(list[dict[str, Any]], job["steps"]):
        if step.get("id") == step_id:
            return str(step["run"])
    raise AssertionError(f"no step with id {step_id}")


def _compose() -> dict[str, Any]:
    return _load_yaml(COMPOSE_PATH)


def _deploy_code() -> str:
    script = DEPLOY_SCRIPT_PATH.read_text(encoding="utf-8")
    return "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))


# ─── Scenario 1: stable release triggers the automated workflow ────────────────


def test_scenario_1_official_release_publishes_and_can_deploy_automatically() -> None:
    triggers = _triggers(_release_workflow())
    deploy = _deploy_job()

    assert triggers["release"]["types"] == ["published"]
    assert "push" not in triggers
    assert deploy["needs"] == ["publish"]
    condition = str(deploy["if"])
    assert "github.event_name == 'release'" in condition
    assert "github.event.release.draft == false" in condition
    assert "github.event.release.prerelease == false" in condition
    assert deploy["environment"] == "production"


# ─── Scenario 2: draft/prerelease are never deployed ─────────────────────────


def test_scenario_2_draft_and_prerelease_releases_are_rejected() -> None:
    resolve = _script("release")
    deploy_condition = str(_deploy_job()["if"])

    # Publish/resolve rejects drafts and prereleases before any image is pushed.
    assert ".draft" in resolve
    assert ".prerelease" in resolve
    assert "draft or a prerelease" in resolve
    # Deploy job is additionally gated to stable published releases.
    assert "github.event.release.draft == false" in deploy_condition
    assert "github.event.release.prerelease == false" in deploy_condition
    # Manual deploy must be explicitly opted in and still names an existing release.
    deploy_input = _triggers(_release_workflow())["workflow_dispatch"]["inputs"]["deploy"]
    assert deploy_input["default"] is False


# ─── Scenario 3-5: build/publish/registry/image availability failures ────────


def test_scenarios_3_to_5_pipeline_is_fail_closed_before_and_during_deploy() -> None:
    publish = _publish_job()
    deploy = _deploy_job()
    code = _deploy_code()

    # A build/push failure happens inside publish; deploy cannot run without publish.
    assert deploy["needs"] == ["publish"]
    step_ids = [step.get("id") for step in cast(list[dict[str, Any]], publish["steps"])]
    assert "build_api" in step_ids
    assert "build_web" in step_ids
    assert "verify" in step_ids

    # Deploy pulls by digest, requires digest refs, and verifies the revision label.
    assert "${COMPOSE[@]} pull" in code or 'pull "api-${target_slot}"' in code
    assert "*@sha256:*" in code
    assert "CHARSOOQ_API_IMAGE must be repository@sha256:<digest>" in code
    assert "CHARSOOQ_WEB_IMAGE must be repository@sha256:<digest>" in code
    assert "org.opencontainers.image.revision" in code
    assert "verify_revision" in code
    # set -euo pipefail means pull/inspect/probe command failures abort deployment.
    assert "set -euo pipefail" in code


# ─── Scenario 6-8: health/smoke/migration failures do not switch traffic ────


def test_scenarios_6_to_8_pre_switch_failures_leave_active_slot_unchanged() -> None:
    code = _deploy_code()

    # Migration is run once on the shared database before the new slot is started.
    migrate_index = code.index('log "applying migrations')
    start_index = code.index('log "starting inactive slot')
    verify_index = code.index('log "verifying inactive slot')
    switch_index = code.index('log "switching traffic to slot')
    assert migrate_index < start_index < verify_index < switch_index

    assert "run --rm migrate" in code
    assert "verify_slot" in code
    assert "/ready" in code
    assert "/health" in code
    assert "/login" in code
    assert "/api/v1/health" in code

    # Failures before the Caddy switch must not move traffic.
    assert "failed to start api-${target_slot}; the active slot was not changed" in code
    assert "failed to start web-${target_slot}; the active slot was not changed" in code
    assert "slot ${target_slot} failed verification; the active slot was not changed" in code
    # Traffic is only rewritten/reloaded at the explicit switch point.
    assert code.count('write_upstream "$target_slot"') == 1
    assert "reload_caddy" in code


# ─── Scenario 9: concurrent deployments are serialized ───────────────────────


def test_scenario_9_concurrent_deployments_are_queued_not_raced() -> None:
    workflow = _release_workflow()
    workflow_concurrency = workflow["concurrency"]
    deploy_concurrency = _deploy_job()["concurrency"]

    assert workflow_concurrency["cancel-in-progress"] is False
    assert "release-images-" in str(workflow_concurrency["group"])
    assert deploy_concurrency == {
        "group": "deploy-production",
        "cancel-in-progress": False,
    }


# ─── Scenario 10: successful traffic switch is verified and recorded ─────────


def test_scenario_10_successful_switch_is_gated_verified_and_persisted() -> None:
    code = _deploy_code()

    # Switch happens only after inactive-slot verification.
    verify_pos = code.index("slot ${target_slot} failed verification")
    switch_pos = code.index('log "switching traffic to slot')
    assert verify_pos < switch_pos

    assert 'write_upstream "$target_slot"' in code
    assert "reload_caddy" in code
    assert "verify_external" in code
    assert "write_state" in code
    assert "ACTIVE_SLOT=${active_slot}" in code
    assert "INACTIVE_SLOT=${inactive_slot}" in code
    assert "RELEASE_SHA=${CHARSOOQ_RELEASE_SHA}" in code
    assert (
        "deployment complete: active slot ${active_slot}; "
        "previous slot ${inactive_slot} kept for rollback"
    ) in code
    # External verification is protocol-aware and must not skip HTTP-only probes.
    assert "CHARSOOQ_PUBLIC_SCHEME" in code
    assert "external HTTP health probe failed" in code
    assert "external HTTPS health probe failed" in code


# ─── Scenario 11: rollback behavior is preserved ─────────────────────────────


def test_scenario_11_previous_slot_is_kept_and_post_switch_failure_returns_traffic() -> None:
    code = _deploy_code()

    assert "kept for rollback" in code
    assert "inactive_slot" in code
    assert "post-switch verification failed; switching traffic back to slot ${active_slot}" in code
    assert 'write_upstream "$active_slot"' in code
    assert "traffic was returned to ${active_slot}" in code
    assert "manual intervention is required" in code
    # Previous release identity is carried in state (when known) for rollback.
    assert 'previous_api="${ACTIVE_API:-}"' in code
    assert 'previous_web="${ACTIVE_WEB:-}"' in code
    assert 'inactive_api="$previous_api"' in code
    assert 'inactive_web="$previous_web"' in code


# ─── Scenario 12: restart preserves active slot selection/state contracts ────


def test_scenario_12_restart_persistence_contracts_are_present() -> None:
    compose = _compose()
    caddy = compose["services"]["caddy"]
    db = compose["services"]["db"]
    volumes = [str(v) for v in caddy.get("volumes", [])]
    code = _deploy_code()

    # Active upstream is a bind-mounted file rewritten on disk (not container-local only).
    assert "./deploy/caddy:/etc/caddy:ro" in volumes
    assert "write_upstream" in code
    assert "ACTIVE_UPSTREAM_FILE" in code
    assert 'mv "$tmp" "$ACTIVE_UPSTREAM_FILE"' in code
    # State is persisted on host and used to detect active slot.
    assert "STATE_FILE" in code
    assert "detect_active_slot" in code
    assert "write_state" in code
    # Core services restart automatically after host/container restart.
    assert db.get("restart") == "unless-stopped"
    assert caddy.get("restart") == "unless-stopped"
    assert compose["services"]["api-blue"].get("restart") == "unless-stopped"
    assert compose["services"]["api-green"].get("restart") == "unless-stopped"
    assert compose["services"]["web-blue"].get("restart") == "unless-stopped"
    assert compose["services"]["web-green"].get("restart") == "unless-stopped"
    # Persistent volumes for database and caddy state remain declared.
    named_volumes = set(compose.get("volumes", {}))
    assert {"pgdata", "caddy_data", "caddy_config"} <= named_volumes
    # Default committed upstream selects a concrete slot (blue by default) for recovery.
    assert re.search(
        r"reverse_proxy web-(blue|green):3000",
        ACTIVE_UPSTREAM_PATH.read_text(encoding="utf-8"),
    )
    assert "X-Forwarded-Port" in ACTIVE_UPSTREAM_PATH.read_text(encoding="utf-8")


# ─── Security: runner/workflow isolation and least privilege ─────────────────


def test_security_runner_and_workflow_access_is_restricted() -> None:
    deploy = _deploy_job()
    triggers = _triggers(_release_workflow())
    ci = _load_yaml(CI_WORKFLOW_PATH)

    assert deploy["runs-on"] == ["self-hosted", "Linux", "charsooq-production"]
    assert deploy["environment"] == "production"
    assert deploy["permissions"] == {"contents": "read"}
    assert "pull_request" not in triggers
    assert "secrets." not in yaml.safe_dump(deploy)

    workflows_dir = REPO_ROOT / ".github" / "workflows"
    for path in workflows_dir.glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        if "charsooq-production" in text:
            assert path.name == "release.yml"
    ci_triggers = _triggers(ci)
    assert "pull_request" in ci_triggers
    for job in cast(dict[str, Any], ci["jobs"]).values():
        assert "self-hosted" not in str(cast(dict[str, Any], job).get("runs-on", ""))


def test_security_docker_and_network_exposure_boundaries_are_enforced() -> None:
    compose = _compose()
    services = compose["services"]
    networks = compose["networks"]

    # Only Caddy publishes host ports and only to the approved bind IP.
    assert {name for name, svc in services.items() if svc.get("ports")} == {"caddy"}
    ports = [str(p) for p in services["caddy"]["ports"]]
    assert all("CHARSOOQ_PROXY_BIND_IP" in p for p in ports)
    assert not any("0.0.0.0" in p or "[::]" in p for p in ports)  # noqa: S104

    # Caddy is isolated and cannot reach backend/edge/API/DB networks.
    caddy_networks = services["caddy"].get("networks")
    assert caddy_networks == ["proxy"] or set(caddy_networks) == {"proxy"}
    assert networks["backend"].get("internal") is True

    # Docker socket never mounted; Caddy filesystem hardened.
    for name, svc in services.items():
        for volume in [str(v) for v in svc.get("volumes", [])]:
            assert "docker.sock" not in volume, name
    assert services["caddy"].get("read_only") is True
    assert "ALL" in services["caddy"].get("cap_drop", [])
    assert "no-new-privileges:true" in services["caddy"].get("security_opt", [])

    # Secrets are least-privilege and file-backed outside repo by default path.
    assert services["migrate"].get("secrets") == ["migration_database_url"]
    assert "postgres_password" not in services["api-blue"].get("secrets", [])
    assert "migration_database_url" not in services["api-blue"].get("secrets", [])
    assert str(compose["secrets"]["database_url"]["file"]).startswith("${CHARSOOQ_SECRETS_DIR")


def test_security_deploy_script_and_runner_prep_do_not_expose_secrets() -> None:
    code = _deploy_code()
    preflight = PREFLIGHT_SCRIPT_PATH.read_text(encoding="utf-8")
    deploy_source = DEPLOY_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "set -x" not in code
    assert "secrets." not in code
    assert "GH_TOKEN" not in code
    assert "down -v" not in code
    assert "system prune" not in code
    assert "volume prune" not in code
    # Non-secret host env file is read; secret file contents are never read/printed.
    assert "CHARSOOQ_ENV_FILE" in code
    assert "never reads or prints a secret value" in deploy_source
    # Preflight/required-var checks must fail closed before state changes.
    assert "CHARSOOQ_EDGE_GREEN_SUBNET" in code
    assert "CHARSOOQ_WEB_GREEN_EDGE_IP" in code
    assert "green slot edge values are missing" in preflight

    assert "set -x" not in preflight
    assert "does NOT read or print secret values" in preflight
    assert "No install/register performed" in preflight
    assert os.access(PREFLIGHT_SCRIPT_PATH, os.X_OK) or (
        PREFLIGHT_SCRIPT_PATH.stat().st_mode & stat.S_IXUSR
    )


def test_runner_preparation_artifacts_and_documentation_exist() -> None:
    assert PREFLIGHT_SCRIPT_PATH.is_file()
    assert (REPO_ROOT / "deploy" / "runner" / "runner.env.example").is_file()
    assert (REPO_ROOT / "deploy" / "runner" / "README.md").is_file()
    assert (REPO_ROOT / "docs" / "operations" / "self-hosted-runner.md").is_file()

    runner_doc_path = REPO_ROOT / "docs" / "operations" / "self-hosted-runner.md"
    runner_doc = runner_doc_path.read_text(encoding="utf-8")
    runner_readme = (REPO_ROOT / "deploy" / "runner" / "README.md").read_text(encoding="utf-8")
    runner_env = (REPO_ROOT / "deploy" / "runner" / "runner.env.example").read_text(
        encoding="utf-8"
    )
    assert "charsooq-production" in runner_doc
    assert "Nothing in this repository installs" in runner_doc
    assert "no runner has been registered" in runner_doc
    assert "No runner is installed or registered" in runner_readme
    assert "registration token" in runner_doc.lower()
    assert "NO registration token" in runner_env
    assert "SECRET" not in runner_env


def test_release_and_deploy_shell_scripts_have_valid_bash_syntax() -> None:
    for path in (
        DEPLOY_SCRIPT_PATH,
        PREFLIGHT_SCRIPT_PATH,
    ):
        result = subprocess.run(  # noqa: S603 - fixed interpreter, no shell
            [BASH, "-n", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    # Workflow release/guard shell blocks are also syntax-checkable as executed today.
    resolve = _script("release")
    guard = _script("guard")
    for block in (resolve, guard):
        result = subprocess.run(  # noqa: S603
            [BASH, "-n", "-c", block],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


# ─── HTTP-only compatibility and preflight/deploy guards (requested) ─────────


def _run_bash_script(
    script: Path, env: dict[str, str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter, no shell
        [BASH, str(script)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(cwd) if cwd else None,
    )


def test_http_only_caddy_configuration_has_no_tls_redirect_or_hsts() -> None:
    caddyfile = (REPO_ROOT / "deploy" / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    site = (REPO_ROOT / "deploy" / "caddy" / "site.caddy").read_text(encoding="utf-8")
    tls_none = (REPO_ROOT / "deploy" / "caddy" / "tls-none.caddy").read_text(encoding="utf-8")
    upstream = ACTIVE_UPSTREAM_PATH.read_text(encoding="utf-8")

    # 1. Caddy supports explicit HTTP-only mode via configuration.
    assert "{$CHARSOOQ_PUBLIC_SCHEME:https}://{$CHARSOOQ_SITE_HOST}" in caddyfile
    assert "auto_https {$CHARSOOQ_CADDY_AUTO_HTTPS:off}" in caddyfile
    assert "import tls-{$CHARSOOQ_TLS_MODE:organization}.caddy" in caddyfile
    # 2. HSTS disabled in HTTP-only (no header in none/site; HTTPS snippets own it).
    assert "Strict-Transport-Security" not in _compose_proxy_text(site)
    assert "Strict-Transport-Security" not in _compose_proxy_text(tls_none)
    assert "tls " not in _compose_proxy_text(tls_none)
    # 3. No forced redirect to HTTPS in HTTP-only: auto_https is config-driven and
    # HTTP-only uses auto_https off + http scheme (no https site block).
    assert "redir https://" not in caddyfile
    # Forwarded headers remain correct and port is config-driven by deploy rewrite.
    assert "header_up X-Forwarded-Proto {scheme}" in upstream
    assert "header_up X-Forwarded-Port" in upstream


def _compose_proxy_text(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def test_external_probe_supports_http_without_skipping_and_https_is_preserved() -> None:
    code = _deploy_code()

    # 4. External probe uses configured protocol; HTTP-only probes over HTTP and
    # missing TLS material must not skip verification. HTTPS remains configurable.
    assert 'base_url="${CHARSOOQ_PUBLIC_SCHEME}://${CHARSOOQ_SITE_HOST}"' in code
    assert 'if [ "$CHARSOOQ_PUBLIC_SCHEME" = "https" ]' in code
    assert "external HTTP health probe failed" in code
    assert "external HTTP login probe failed" in code
    assert "external HTTPS health probe failed" in code
    assert "external HTTPS login probe failed" in code
    assert 'curl -fsS "${base_url}/api/v1/health"' in code
    assert "skipping external HTTPS probes" not in code
    # HTTPS requires CA file and host config; missing required address/config fails.
    assert "CHARSOOQ_CA_FILE must be set for HTTPS external verification" in code


def test_deploy_fails_before_any_change_when_green_variables_are_missing(tmp_path: Path) -> None:
    compose = tmp_path / "compose.production.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    upstream = tmp_path / "active-upstream.caddy"
    upstream.write_text("reverse_proxy web-blue:3000 {}\n", encoding="utf-8")
    env_file = tmp_path / "production.env"
    env_file.write_text(
        "\n".join(
            [
                "CHARSOOQ_PROXY_BIND_IP=192.0.2.10",
                "CHARSOOQ_SITE_HOST=charsooq.internal",
                "CHARSOOQ_EDGE_BLUE_SUBNET=192.0.2.0/28",
                "CHARSOOQ_WEB_BLUE_EDGE_IP=192.0.2.11",
                # green vars intentionally missing
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_file = state_dir / "deploy-state.env"
    before_upstream = upstream.read_text(encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "CHARSOOQ_COMPOSE_FILE": str(compose),
            "CHARSOOQ_ENV_FILE": str(env_file),
            "CHARSOOQ_STATE_DIR": str(state_dir),
            "CHARSOOQ_STATE_FILE": str(state_file),
            "CHARSOOQ_ACTIVE_UPSTREAM_FILE": str(upstream),
            "CHARSOOQ_API_IMAGE": "ghcr.io/example/api@sha256:" + "1" * 64,
            "CHARSOOQ_WEB_IMAGE": "ghcr.io/example/web@sha256:" + "2" * 64,
            "CHARSOOQ_RELEASE_SHA": "a" * 40,
            "CHARSOOQ_PUBLIC_SCHEME": "http",
            "PATH": "",  # prevent docker/compose/curl side effects if reached
        }
    )

    result = _run_bash_script(DEPLOY_SCRIPT_PATH, env)

    # 5. Missing green vars stop deployment before any state change.
    assert result.returncode != 0
    assert "CHARSOOQ_EDGE_GREEN_SUBNET" in (result.stderr + result.stdout)
    assert upstream.read_text(encoding="utf-8") == before_upstream
    assert not state_file.exists()


def test_deploy_fails_before_state_change_when_upstream_file_not_writable(tmp_path: Path) -> None:
    compose = tmp_path / "compose.production.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    upstream = tmp_path / "active-upstream.caddy"
    upstream.write_text("reverse_proxy web-blue:3000 {}\n", encoding="utf-8")
    upstream.chmod(0o444)
    env_file = tmp_path / "production.env"
    env_file.write_text(
        "\n".join(
            [
                "CHARSOOQ_PROXY_BIND_IP=192.0.2.10",
                "CHARSOOQ_SITE_HOST=charsooq.internal",
                "CHARSOOQ_EDGE_BLUE_SUBNET=192.0.2.0/28",
                "CHARSOOQ_WEB_BLUE_EDGE_IP=192.0.2.11",
                "CHARSOOQ_EDGE_GREEN_SUBNET=192.0.2.16/28",
                "CHARSOOQ_WEB_GREEN_EDGE_IP=192.0.2.17",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_file = state_dir / "deploy-state.env"
    before_upstream = upstream.read_text(encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "CHARSOOQ_COMPOSE_FILE": str(compose),
            "CHARSOOQ_ENV_FILE": str(env_file),
            "CHARSOOQ_STATE_DIR": str(state_dir),
            "CHARSOOQ_STATE_FILE": str(state_file),
            "CHARSOOQ_ACTIVE_UPSTREAM_FILE": str(upstream),
            "CHARSOOQ_API_IMAGE": "ghcr.io/example/api@sha256:" + "1" * 64,
            "CHARSOOQ_WEB_IMAGE": "ghcr.io/example/web@sha256:" + "2" * 64,
            "CHARSOOQ_RELEASE_SHA": "a" * 40,
            "CHARSOOQ_PUBLIC_SCHEME": "http",
            "PATH": os.environ.get("PATH", ""),
        }
    )
    # Provide curl to pass command check but ensure no compose/docker mutations occur.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("curl", "docker"):
        p = bin_dir / name
        p.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        p.chmod(0o755)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"

    result = _run_bash_script(DEPLOY_SCRIPT_PATH, env)

    # 6. Preflight/required checks fail before upstream/state changes.
    assert result.returncode != 0
    assert "active upstream file is not writable" in (result.stderr + result.stdout)
    assert upstream.read_text(encoding="utf-8") == before_upstream
    assert not state_file.exists()


def test_session_cookie_secure_remains_false_for_current_http_only_slots() -> None:
    services = _compose()["services"]
    # 7. Preserve current temporary HTTP-only setting.
    assert services["api-blue"]["environment"]["SESSION_COOKIE_SECURE"] == "false"
    assert services["api-green"]["environment"]["SESSION_COOKIE_SECURE"] == "false"


def test_https_configuration_remains_possible_in_future() -> None:
    caddyfile = (REPO_ROOT / "deploy" / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    compose = _compose()
    env_example = (REPO_ROOT / "deploy" / "production.env.example").read_text(encoding="utf-8")

    # 8. HTTPS remains configurable (no migration to HTTPS performed now).
    assert "CHARSOOQ_PUBLIC_SCHEME" in caddyfile
    assert (REPO_ROOT / "deploy" / "caddy" / "tls-organization.caddy").is_file()
    assert (REPO_ROOT / "deploy" / "caddy" / "tls-internal-ca.caddy").is_file()
    assert "fullchain.pem" in _compose_proxy_text(
        (REPO_ROOT / "deploy" / "caddy" / "tls-organization.caddy").read_text(encoding="utf-8")
    )
    assert (
        compose["services"]["caddy"]["environment"]["CHARSOOQ_TLS_MODE"]
        == "${CHARSOOQ_TLS_MODE:-organization}"
    )
    assert "CHARSOOQ_PUBLIC_SCHEME=https" in env_example
    assert "HTTPS (future" in env_example


def test_workflow_actions_remain_pinned_to_commit_shas() -> None:
    pinned = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")
    for workflow in (_release_workflow(), _load_yaml(CI_WORKFLOW_PATH)):
        stack: list[object] = [workflow]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for key, value in cast(dict[object, object], node).items():
                    if key == "uses" and isinstance(value, str) and not value.startswith("."):
                        assert pinned.match(value), f"{value} is not pinned to a commit SHA"
                    elif isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(node, list):
                stack.extend(cast(list[object], node))
