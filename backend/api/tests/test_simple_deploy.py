"""Single-slot Production deploy contract (offline, no Production contact).

The script is executed only against temporary files and fake `docker`/`curl`
binaries: no registry, daemon, host, secret file, or Production stack is touched.
"""

from __future__ import annotations

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


def _code() -> str:
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    return "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))


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
                "CHARSOOQ_API_REPO=ghcr.io/example/charsooq-api",
                "CHARSOOQ_WEB_REPO=ghcr.io/example/charsooq-web",
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
) -> tuple[Path, Path]:
    """Install fake docker/curl. The docker fake answers both digest lookups and
    the OCI label reads the deploy script uses to reject a mixed release."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"
    web_version = web_version or api_version
    web_revision = web_revision or api_revision
    answer_digest = digest or "sha256:" + "1" * 64

    def label_json(version: str, revision: str) -> str:
        return (
            '{"config":{"Labels":{'
            f'"org.opencontainers.image.version":"{version}",'
            f'"org.opencontainers.image.revision":"{revision}"'
            "}}}"
        )

    docker = bin_dir / "docker"
    docker.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f'printf "%s\\n" "$*" >> "{docker_log}"',
                'case "$*" in',
                '  *" imagetools inspect "*)',
                '    case "$*" in',
                '      *"{{json .Image}}"*)',
                '        case "$*" in',
                "          *charsooq-web*)",
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
                '  *" ps "*)',
                '    printf "%s\\n" fake-caddy-id',
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
        "#!/bin/sh\n" + f'printf "%s\\n" "$*" >> "{curl_log}"\n' + "exit 0\n",
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


def test_no_argument_deploys_the_latest_release(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env)

    result = _run([], env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "resolving 'latest' to image digests" in result.stdout
    commands = docker_log.read_text()
    assert "ghcr.io/example/charsooq-api:latest" in commands
    assert "ghcr.io/example/charsooq-web:latest" in commands
    assert "release 1.2.3 (" + REVISION + ")" in result.stdout
    assert "deployment complete (1.2.3)" in result.stdout


def test_a_tag_deploy_resolves_digests_and_runs_the_ordered_single_slot_flow(
    tmp_path: Path,
) -> None:
    env = _fixture(tmp_path)
    docker_log, curl_log = _fake_bin(tmp_path, env)

    result = _run(["v1.2.3"], env)

    assert result.returncode == 0, result.stderr + result.stdout
    commands = docker_log.read_text()
    assert "charsooq-api:v1.2.3" in commands
    assert "charsooq-web:v1.2.3" in commands
    digest = "sha256:" + "1" * 64
    assert "ghcr.io/example/charsooq-api@" + digest in result.stdout
    assert "ghcr.io/example/charsooq-web@" + digest in result.stdout

    pull = commands.index("pull api web")
    provision = commands.index("run --rm provision")
    migrate = commands.index("run --rm migrate")
    up = commands.index("up -d --no-build --remove-orphans")
    assert pull < provision < migrate < up
    assert "kill --signal=USR1 fake-caddy-id" in commands

    probes = curl_log.read_text()
    assert "/api/v1/health" in probes
    assert "/login" in probes


def test_explicit_digest_deploy_skips_tag_resolution(tmp_path: Path) -> None:
    env = _fixture(tmp_path)
    docker_log, _ = _fake_bin(tmp_path, env)
    api = "ghcr.io/example/charsooq-api@sha256:" + "a" * 64
    web = "ghcr.io/example/charsooq-web@sha256:" + "b" * 64

    result = _run([api, web], env)

    assert result.returncode == 0, result.stderr + result.stdout
    commands = docker_log.read_text()
    assert "imagetools inspect" in commands  # label check only, no digest lookup
    assert ":latest" not in commands
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
