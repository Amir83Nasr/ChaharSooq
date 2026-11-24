"""Single-slot Production deploy contract (offline, no Production contact).

The script is executed only against temporary files and fake `docker`/`curl`
binaries: no registry, GitHub, daemon, host, secret file, or Production stack is
touched.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEPLOY_SCRIPT = REPO_ROOT / "deploy" / "scripts" / "deploy.sh"
BASH = shutil.which("bash") or "/bin/bash"

SECRET_NAMES = (
    "postgres_password",
    "database_url",
    "migration_database_url",
    "session_secret",
    "owner_password",
    "parsina_password",
)
REVISION = "a" * 40
PREVIOUS_VERSION = "1.2.2"
CHECK_AT_HEAD = "migrate: database already at head"
CHECK_PENDING = "migrate: migrations pending"


def _code() -> str:
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    return "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))


def _release_json(
    tag: str = "v1.2.3",
    *,
    draft: bool = False,
    prerelease: bool = False,
    commit: str = REVISION,
) -> str:
    return json.dumps(
        {
            "tag_name": tag,
            "draft": draft,
            "prerelease": prerelease,
            "target_commitish": commit,
        }
    )


def _fixture(tmp_path: Path) -> dict[str, str]:
    compose = tmp_path / "compose.production.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    env_file = tmp_path / "production.env"
    env_file.write_text(
        "\n".join(
            [
                "CHARSOOQ_PROXY_BIND_IP=192.0.2.10",
                "CHARSOOQ_SITE_HOST=charsooq.example.test",
                "CHARSOOQ_EDGE_SUBNET=192.0.2.0/28",
                "CHARSOOQ_WEB_EDGE_IP=192.0.2.11",
                "CHARSOOQ_PUBLIC_SCHEME=http",
                "CHAHARSOQ_API_REPO=ghcr.io/example/chaharsooq-api",
                "CHAHARSOQ_WEB_REPO=ghcr.io/example/chaharsooq-web",
                "CHARSOOQ_GITHUB_REPO=Amir83Nasr/ChaharSooq",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(exist_ok=True)
    for name in SECRET_NAMES:
        (secret_dir / name).write_text("placeholder", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "CHARSOOQ_COMPOSE_FILE": str(compose),
            "CHARSOOQ_ENV_FILE": str(env_file),
            "CHARSOOQ_SECRETS_DIR": str(secret_dir),
            "GITHUB_TOKEN": "",
            "NO_COLOR": "1",
            "PATH": "",  # no docker/curl available unless a test installs fakes
        }
    )
    return env


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter, no shell
        [BASH, str(DEPLOY_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _fake_bin(
    tmp_path: Path,
    env: dict[str, str],
    *,
    digest: str = "",
    api_version: str = "1.2.3",
    web_version: str | None = None,
    api_revision: str = REVISION,
    web_revision: str | None = None,
    pretty: bool = False,
    release_json: str | None = None,
    migration_pending: bool = False,
    migration_check_fails: bool = False,
    migration_check_unsupported: bool = False,
    previous_version: str = PREVIOUS_VERSION,
    cluster_major: str = "19",
    db_image: str = "postgres:19.0-trixie",
    api_state: str = "healthy",
) -> tuple[Path, Path]:
    """Install fake docker/curl. The docker fake answers digest lookups, OCI
    label reads, container state, the cluster-version guard, and the migration
    check used to avoid a redundant upgrade run."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"
    web_version = web_version or api_version
    web_revision = web_revision or api_revision
    answer_digest = digest or "sha256:" + "1" * 64
    release = release_json if release_json is not None else _release_json()
    check_message = CHECK_PENDING if migration_pending else CHECK_AT_HEAD
    compose_json = json.dumps({"services": {"db": {"image": db_image}}})

    def label_json(version: str, revision: str) -> str:
        labels = {
            "org.opencontainers.image.version": version,
            "org.opencontainers.image.revision": revision,
        }
        if pretty:
            return json.dumps({"config": {"Labels": labels}}, indent=2)
        return (
            '{"config":{"Labels":{'
            f'"org.opencontainers.image.version":"{version}",'
            f'"org.opencontainers.image.revision":"{revision}"'
            "}}}"
        )

    if migration_check_unsupported:
        check_branch = '    printf "%s\\n" "usage: migrate.py [--check]" >&2; exit 1'
    elif migration_check_fails:
        check_branch = '    printf "%s\\n" "migrate: check failed" >&2; exit 1'
    else:
        check_branch = f'    printf "%s\\n" "{check_message}"'
    docker = bin_dir / "docker"
    docker.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f'printf "%s\\n" "$*" >> "{docker_log}"',
                'case "$*" in',
                f"  *\"config --format json\"*) printf '%s\\n' '{compose_json}' ;;",
                f'  *"--entrypoint sh db"*) printf "%s\\n" "{cluster_major}" ;;',
                '  *" imagetools inspect "*)',
                '    case "$*" in',
                '      *"{{json .Image}}"*)',
                '        case "$*" in',
                "          *chaharsooq-web*)",
                f"            printf '%s\\n' '{label_json(web_version, web_revision)}'",
                "            ;;",
                "          *)",
                f"            printf '%s\\n' '{label_json(api_version, api_revision)}'",
                "            ;;",
                "        esac",
                "        ;;",
                "      *)",
                f'        printf "%s\\n" "{answer_digest}"',
                "        ;;",
                "    esac",
                "    ;;",
                '  *"migrate.py --check"*)',
                check_branch,
                "    ;;",
                "  inspect*--format*)",
                '    case "$*" in',
                '      *".State.Health"*)',
                '        case "$*" in',
                '          *fake-caddy-id*) printf "%s\\n" "running" ;;',
                f'          *fake-api-id*) printf "%s\\n" "{api_state}" ;;',
                '          *) printf "%s\\n" "healthy" ;;',
                "        esac",
                "        ;;",
                '      *"org.opencontainers.image.version"*)',
                f'        printf "%s\\n" "{previous_version}" ;;',
                "      *) exit 0 ;;",
                "    esac",
                "    ;;",
                '  *" ps "*)',
                '    case "$*" in',
                '      *"ps -q caddy"*) printf "%s\\n" fake-caddy-id ;;',
                '      *"ps -q api"*) printf "%s\\n" fake-api-id ;;',
                '      *) printf "%s\\n" fake-service-id ;;',
                "    esac",
                "    ;;",
                "esac",
                "exit 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    curl = bin_dir / "curl"
    curl.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f'printf "%s\\n" "$*" >> "{curl_log}"',
                'case "$*" in',
                f"  *\"api.github.com/repos/\"*) printf '%s\\n' '{release}' ;;",
                "esac",
                "exit 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    curl.chmod(0o755)
    env["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"
    return docker_log, curl_log


def test_the_script_is_valid_bash() -> None:
    result = subprocess.run([BASH, "-n", str(DEPLOY_SCRIPT)], capture_output=True, text=True)  # noqa: S603
    assert result.returncode == 0, result.stderr


def test_no_blue_green_or_runner_machinery_remains() -> None:
    code = _code()
    for removed in (
        "detect_active_slot",
        "write_upstream",
        "active-upstream.caddy",
        "ACTIVE_SLOT",
        "STATE_FILE",
        "--profile",
        "self-hosted",
    ):
        assert removed not in code
    assert "reverse_proxy" not in code
    assert "up -d --no-build --remove-orphans" in code
    assert "image_label" in code
    assert "different versions" in code


def test_fail_closed_before_any_change_when_a_required_value_is_missing(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    env["CHARSOOQ_ENV_FILE"] = str(tmp_path / "missing.env")

    result = _run([], env)

    assert result.returncode != 0
    assert "CHARSOOQ_PROXY_BIND_IP" in result.stderr


def test_fail_closed_when_the_secret_directory_is_missing(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    env["CHARSOOQ_SECRETS_DIR"] = str(tmp_path / "missing-secrets")

    result = _run([], env)

    assert result.returncode != 0
    assert "secret directory not found" in result.stderr


def test_the_script_never_reads_or_prints_a_secret() -> None:
    code = _code()
    for name in SECRET_NAMES:
        assert name not in code


def test_fail_closed_when_a_tag_cannot_be_resolved_to_a_digest(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    _fake_bin(tmp_path, env, digest="not-a-digest")

    result = _run(["v1.2.3"], env)

    assert result.returncode != 0
    assert "cannot resolve a digest" in result.stderr


def test_cluster_major_mismatch_stops_the_deploy_before_any_change(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, curl_log = _fake_bin(tmp_path, env, cluster_major="18")

    result = _run(["v1.2.3"], env)

    assert result.returncode != 0
    assert "cluster is PostgreSQL 18 but the image is postgres:19.0-trixie" in result.stderr
    commands = docker_log.read_text()
    assert "/var/lib/postgresql/19/docker/PG_VERSION" in commands
    assert "pull api web" not in commands
    assert "up -d --no-build --remove-orphans" not in commands
    assert not curl_log.exists()


def test_missing_cluster_stops_the_deploy(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    _fake_bin(tmp_path, env, cluster_major="")

    result = _run([], env)

    assert result.returncode != 0
    assert "no PostgreSQL 19 cluster in the pgdata volume" in result.stderr


def test_no_argument_uses_the_newest_published_github_release(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, curl_log = _fake_bin(tmp_path, env)

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "releases/latest" in curl_log.read_text()
    commands = docker_log.read_text()
    assert "chaharsooq-api:1.2.3" in commands
    assert "chaharsooq-web:1.2.3" in commands
    assert ":latest" not in commands
    assert "Release     v1.2.3 (" + REVISION + ")" in result.stdout
    assert "deployment complete (1.2.3)" in result.stdout


def test_a_tag_deploy_fetches_that_release_and_runs_the_ordered_flow(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, curl_log = _fake_bin(tmp_path, env)

    result = _run(["v1.2.3"], env)

    assert result.returncode == 0, result.stderr + result.stdout
    commands = docker_log.read_text()
    assert "releases/tags/v1.2.3" in curl_log.read_text()
    assert "chaharsooq-api:1.2.3" in commands
    assert "chaharsooq-web:1.2.3" in commands
    assert ":v1.2.3" not in commands
    digest = "sha256:" + "1" * 64
    assert "ghcr.io/example/chaharsooq-api@" + digest in result.stdout
    assert "ghcr.io/example/chaharsooq-web@" + digest in result.stdout

    pull = commands.index("pull api web")
    provision = commands.index("run --rm provision")
    check = commands.index("migrate.py --check")
    up = commands.index("up -d --no-build --remove-orphans")
    assert pull < provision < check < up
    assert "kill --signal=USR1 fake-caddy-id" in commands

    probes = curl_log.read_text()
    for endpoint in ("/api/v1/health", "/api/v1/ready", "/login"):
        assert endpoint in probes


def test_explicit_digest_deploy_skips_github_and_tag_resolution(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, curl_log = _fake_bin(tmp_path, env)
    api = "ghcr.io/example/chaharsooq-api@sha256:" + "a" * 64
    web = "ghcr.io/example/chaharsooq-web@sha256:" + "b" * 64

    result = _run([api, web], env)

    assert result.returncode == 0, result.stderr + result.stdout
    commands = docker_log.read_text()
    assert "imagetools inspect" in commands  # label check only, no digest lookup
    assert ":latest" not in commands
    assert "api.github.com" not in curl_log.read_text()
    assert "GitHub release discovery skipped" in result.stdout
    assert api in result.stdout
    assert web in result.stdout


def test_mixed_release_is_rejected_before_any_change(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env, web_version="9.9.9")

    result = _run([], env)

    assert result.returncode != 0
    assert "different versions ('1.2.3' vs '9.9.9')" in result.stderr
    commands = docker_log.read_text()
    assert "pull api web" not in commands
    assert "up -d" not in commands


def test_image_version_must_match_the_github_release(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    _fake_bin(tmp_path, env, api_version="9.9.9", web_version="9.9.9")

    result = _run([], env)

    assert result.returncode != 0
    assert "does not match GitHub release v1.2.3" in result.stderr


def test_image_commit_must_match_the_release_commit(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env, release_json=_release_json(commit="b" * 40))

    result = _run([], env)

    assert result.returncode != 0
    assert "does not match release commit" in result.stderr
    assert "pull api web" not in docker_log.read_text()


def test_draft_and_prerelease_releases_are_rejected(tmp_path: Path) -> None:
    for draft, prerelease in ((True, False), (False, True)):
        env = _fixture(tmp_path)
        release = _release_json(draft=draft, prerelease=prerelease)
        docker_log, _ = _fake_bin(tmp_path, env, release_json=release)

        result = _run([], env)

        assert result.returncode != 0
        assert "release v1.2.3 is" in result.stderr
        commands = docker_log.read_text() if docker_log.exists() else ""
        assert "pull api web" not in commands


def test_invalid_release_tag_is_rejected(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    _fake_bin(tmp_path, env, release_json=_release_json(tag="release-123"))

    result = _run([], env)

    assert result.returncode != 0
    assert "unexpected release tag 'release-123'" in result.stderr


def test_missing_github_repo_reads_release_body_and_fails_without_digests(
    tmp_path: Path,
) -> None:
    env = _fixture(tmp_path)
    _fake_bin(tmp_path, env)
    env_file = Path(env["CHARSOOQ_ENV_FILE"])
    original = env_file.read_text(encoding="utf-8")
    env_file.write_text(
        original.replace("CHARSOOQ_GITHUB_REPO=", "CHARSOOQ_GITHUB_REPO_UNUSED="),
        encoding="utf-8",
    )

    result = _run([], env)

    assert result.returncode != 0
    assert "release body has no CHAHARSOQ_API_IMAGE digest" in result.stderr
    assert "reading digests from the newest published release" in result.stdout


def test_release_body_digests_are_used_without_repo_or_env_refs(tmp_path: Path) -> None:
    """`make prod-deploy VERSION=vX.Y.Z` works with only network values in env."""
    env = _fixture(tmp_path)
    docker_log, curl_log = _fake_bin(tmp_path, env)
    env_file = Path(env["CHARSOOQ_ENV_FILE"])
    original = env_file.read_text(encoding="utf-8")
    env_file.write_text(
        original.replace("CHARSOOQ_GITHUB_REPO=", "CHARSOOQ_GITHUB_REPO_UNUSED="),
        encoding="utf-8",
    )
    api = "ghcr.io/amir83nasr/chaharsooq-api@sha256:" + "a" * 64
    web = "ghcr.io/amir83nasr/chaharsooq-web@sha256:" + "b" * 64
    release = _release_json()
    import json as _json

    body = (
        "ChaharSooq release v1.2.3.\n\n"
        f'export CHAHARSOQ_API_IMAGE="{api}"\n'
        f'export CHAHARSOQ_WEB_IMAGE="{web}"\n'
    )
    release = _json.dumps({**_json.loads(release), "body": body})
    import shutil as _shutil

    # reinstall the fake with the richer release body
    bin_dir = tmp_path / "bin"
    _shutil.rmtree(bin_dir)
    _, curl_log = _fake_bin(tmp_path, env, release_json=release)

    result = _run(["v1.2.3"], env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "digest-pinned image references from the release body" in result.stdout
    assert api in result.stdout
    assert web in result.stdout
    assert "releases/tags/v1.2.3" in curl_log.read_text()


def test_env_file_digests_work_without_github_discovery(tmp_path: Path) -> None:
    """A host without GitHub access can pin both digests in the env file."""
    env = _fixture(tmp_path)
    docker_log, curl_log = _fake_bin(tmp_path, env)
    env_file = Path(env["CHARSOOQ_ENV_FILE"])
    original = env_file.read_text(encoding="utf-8")
    api = "ghcr.io/example/chaharsooq-api@sha256:" + "a" * 64
    web = "ghcr.io/example/chaharsooq-web@sha256:" + "b" * 64
    env_file.write_text(
        original.replace("CHARSOOQ_GITHUB_REPO=", "CHARSOOQ_GITHUB_REPO_UNUSED=")
        + f"CHAHARSOQ_API_IMAGE={api}\nCHAHARSOQ_WEB_IMAGE={web}\n",
        encoding="utf-8",
    )

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "digest-pinned image references" in result.stdout
    assert "api.github.com" not in curl_log.read_text()
    assert api in result.stdout
    assert web in result.stdout
    assert "pull api web" in docker_log.read_text()


def test_label_reading_tolerates_formatted_json(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    _fake_bin(tmp_path, env, pretty=True, api_version="1.2.3", web_version="1.2.3")

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Release     v1.2.3 (" + REVISION + ")" in result.stdout


def test_up_to_date_database_skips_the_migration_run(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env)

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    lines = docker_log.read_text().splitlines()
    assert sum("migrate.py --check" in line for line in lines) == 1
    assert not any(line.endswith("run --rm migrate") for line in lines)
    assert "(skip) database already at head" in result.stdout
    assert "Database    already at head" in result.stdout


def test_pending_migrations_are_applied_before_the_api_starts(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env, migration_pending=True)

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    lines = docker_log.read_text().splitlines()
    apply_lines = [index for index, line in enumerate(lines) if line.endswith("run --rm migrate")]
    assert len(apply_lines) == 1
    check_line = next(index for index, line in enumerate(lines) if "migrate.py --check" in line)
    up_line = next(index for index, line in enumerate(lines) if "up -d --no-build" in line)
    assert check_line < apply_lines[0] < up_line
    assert "applying pending migrations" in result.stdout
    assert "Database    applied" in result.stdout


def test_migration_check_failure_stops_before_starting_services(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env, migration_check_fails=True)

    result = _run([], env)

    assert result.returncode != 0
    assert "migration check failed" in result.stderr
    assert "up -d" not in docker_log.read_text()


def test_older_image_without_check_flag_still_deploys(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env, migration_check_unsupported=True)

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "no --check support" in result.stdout
    lines = docker_log.read_text().splitlines()
    assert any(line.endswith("run --rm migrate") for line in lines)
    assert "Database    checked by runner" in result.stdout


def test_progress_and_completion_report_services_health_and_rollback(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    _fake_bin(tmp_path, env, previous_version=PREVIOUS_VERSION)

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    for marker in (
        "[1/10]",
        "[10/10]",
        "Deployment summary",
        "db=healthy",
        "api=healthy",
        "web=healthy",
        "caddy=running",
        "/api/v1/ready ok",
        "All services are up and every health probe passed",
        "./deploy/scripts/deploy.sh v1.2.2",
        "code-only rollback is NOT sufficient",
    ):
        assert marker in result.stdout


def test_cluster_major_mismatch_points_to_the_cutover_runbook(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env, cluster_major="18")

    result = _run([], env)

    assert result.returncode != 0
    assert "pg19_cutover.sh" in result.stderr
    assert "pg_upgrade_drill.sh" in result.stderr
    assert "pull api web" not in docker_log.read_text()


def test_cluster_major_is_rechecked_before_starting_services(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env)

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    marker_reads = [line for line in docker_log.read_text().splitlines() if "PG_VERSION" in line]
    assert len(marker_reads) == 2
    up_line = next(
        index
        for index, line in enumerate(docker_log.read_text().splitlines())
        if "up -d --no-build" in line
    )
    assert all(
        index < up_line
        for index, line in enumerate(docker_log.read_text().splitlines())
        if "PG_VERSION" in line
    )


def test_api_must_report_healthy_not_just_running(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    _fake_bin(tmp_path, env, api_state="running")

    result = _run([], env)

    assert result.returncode != 0
    assert "health verification failed" in result.stderr


def test_stopped_legacy_containers_are_removed_after_starting(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env)

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    commands = docker_log.read_text()
    assert "ps -aq --filter name=^/charsooq-production-" in commands
    assert "status=exited" in commands


def test_rollback_tag_is_normalized_when_the_label_already_has_the_v_prefix(
    tmp_path: Path,
) -> None:
    env = _fixture(tmp_path)
    _fake_bin(tmp_path, env, previous_version="v1.2.2")

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "./deploy/scripts/deploy.sh v1.2.2" in result.stdout
    assert "vv1.2.2" not in result.stdout
