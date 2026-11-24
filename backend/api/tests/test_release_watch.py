"""Outbound-only auto-deploy agent contract (offline, no Production contact).

The script runs only against temporary files and fake `docker`/`curl`/`flock`
binaries; no GitHub, registry, daemon, secret file or Production stack is touched.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WATCH_SCRIPT = REPO_ROOT / "deploy" / "scripts" / "release_watch.sh"
BASH = shutil.which("bash") or "/bin/bash"


def _fixture(
    tmp_path: Path, tag: str = "v0.1.12", *, draft: bool = False, prerelease: bool = False
) -> dict[str, str]:
    env_file = tmp_path / "production.env"
    env_file.write_text(
        "\n".join(
            [
                "CHARSOOQ_PROXY_BIND_IP=192.0.2.10",
                "CHARSOOQ_SITE_HOST=charsooq.example.test",
                "CHARSOOQ_EDGE_SUBNET=192.0.2.0/28",
                "CHARSOOQ_WEB_EDGE_IP=192.0.2.11",
                "CHARSOOQ_PUBLIC_SCHEME=http",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    state = tmp_path / "state" / "last-release"
    state.parent.mkdir(exist_ok=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "calls.log"

    (bin_dir / "docker").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    api = "ghcr.io/amir83nasr/chaharsooq-api@sha256:" + "a" * 64
    web = "ghcr.io/amir83nasr/chaharsooq-web@sha256:" + "b" * 64
    body = f'export CHAHARSOQ_API_IMAGE="{api}"\nexport CHAHARSOQ_WEB_IMAGE="{web}"\n'
    release = json.dumps({"tag_name": tag, "draft": draft, "prerelease": prerelease, "body": body})
    (bin_dir / "curl").write_text(
        f"#!/bin/sh\nprintf '%s\\n' '{release}'\n",
        encoding="utf-8",
    )
    # flock is needed by the script; allow toggling failure for the lock test.
    # The script calls `flock -n 9` with no command: just acquire and return.
    (bin_dir / "flock").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    # Deploy shim: replace the real deploy.sh via CHARSOOQ_WATCH_DEPLOY_SCRIPT.
    deploy = tmp_path / "deploy.sh"
    deploy.write_text(
        f"#!/bin/sh\nprintf 'DEPLOY %s\\n' \"$*\" >> '{log}'\nexit ${{FAKE_DEPLOY_RC:-0}}\n",
        encoding="utf-8",
    )
    deploy.chmod(0o755)
    for name in ("docker", "curl", "flock"):
        (bin_dir / name).chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "CHARSOOQ_ENV_FILE": str(env_file),
            "CHARSOOQ_WATCH_STATE_FILE": str(state),
            "CHARSOOQ_WATCH_LOCK_FILE": str(tmp_path / "watch.lock"),
            "CHARSOOQ_WATCH_DEPLOY_SCRIPT": str(deploy),
            "NO_COLOR": "1",
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        }
    )
    env.pop("FAKE_DEPLOY_RC", None)
    return env


def _run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter, no shell
        [BASH, str(WATCH_SCRIPT)], capture_output=True, text=True, check=False, env=env
    )


def test_valid_bash() -> None:
    result = subprocess.run([BASH, "-n", str(WATCH_SCRIPT)], capture_output=True, text=True)  # noqa: S603
    assert result.returncode == 0, result.stderr


def test_new_release_is_deployed_and_recorded(tmp_path: Path) -> None:
    env = _fixture(tmp_path, "v0.1.12")
    result = _run(env)

    assert result.returncode == 0, result.stderr + result.stdout
    log = tmp_path / "calls.log"
    assert "ghcr.io/amir83nasr/chaharsooq-api@sha256:" in log.read_text()
    assert "ghcr.io/amir83nasr/chaharsooq-web@sha256:" in log.read_text()
    assert (tmp_path / "state" / "last-release").read_text().strip() == "v0.1.12"


def test_same_release_is_not_deployed_twice(tmp_path: Path) -> None:
    env = _fixture(tmp_path, "v0.1.12")
    (tmp_path / "state" / "last-release").write_text("v0.1.12\n")

    result = _run(env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "already deployed" in result.stdout
    assert not (tmp_path / "calls.log").exists()


def test_failed_deploy_does_not_advance_state(tmp_path: Path) -> None:
    env = _fixture(tmp_path, "v0.1.12")
    env["FAKE_DEPLOY_RC"] = "1"

    result = _run(env)

    assert result.returncode != 0
    assert "state file was not updated" in result.stderr
    assert not (tmp_path / "state" / "last-release").exists()


def test_draft_and_prerelease_are_skipped(tmp_path: Path) -> None:
    for draft, prerelease in ((True, False), (False, True)):
        path = tmp_path / f"case-{draft}-{prerelease}"
        path.mkdir()
        env = _fixture(path, "v0.1.12", draft=draft, prerelease=prerelease)

        result = _run(env)

        assert result.returncode == 0, result.stderr + result.stdout
        assert not (path / "calls.log").exists()
