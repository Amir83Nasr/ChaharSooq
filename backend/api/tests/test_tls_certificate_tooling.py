"""Offline TLS tooling and certificate-material hygiene.

The tests generate a throwaway PKI with the system OpenSSL under pytest's
temporary directory (outside the repository), exercise the validation tool, and
remove the material at the end of the session. No real certificate, private key,
or network endpoint is involved.

They also assert that certificate material cannot enter Git or a Docker image.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL = REPO_ROOT / "deploy" / "tls" / "validate_certificate.py"
ACTIVATE_TOOL = REPO_ROOT / "deploy" / "tls" / "activate_certificate.py"
COMPOSE_PATH = REPO_ROOT / "compose.production.yml"
CERT_EXTENSIONS = (".pem", ".key", ".crt", ".cer", ".der", ".p12", ".pfx")
PEM_BODY = re.compile(r"-----BEGIN [A-Z0-9 ]+-----[\r\n]+[A-Za-z0-9+/=\r\n]{64,}")
OPENSSL = shutil.which("openssl") or "openssl"


@dataclass(frozen=True)
class Pki:
    """Throwaway certificate authority and leaf material for one session."""

    root_cert: Path
    root_key: Path
    intermediate_cert: Path
    intermediate_key: Path
    leaf_cert: Path
    leaf_key: Path
    leaf_fullchain: Path
    direct_leaf_cert: Path
    direct_leaf_key: Path
    wrong_host_cert: Path
    wrong_host_key: Path
    wrong_host_fullchain: Path
    no_san_cert: Path
    no_san_key: Path
    no_san_fullchain: Path
    expired_cert: Path
    expired_key: Path
    other_key: Path


def _openssl(*arguments: str) -> None:
    result = subprocess.run(  # noqa: S603 - fixed binary, argument list, no shell
        [OPENSSL, *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"openssl {' '.join(arguments)} failed:\n{result.stderr}")


def _generate_key(path: Path) -> None:
    _openssl("ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(path))


def _generate_csr(key: Path, common_name: str) -> Path:
    request = key.with_suffix(".csr")
    _openssl("req", "-new", "-key", str(key), "-subj", f"/CN={common_name}", "-out", str(request))
    return request


def _self_signed_ca(certificate: Path, key: Path, common_name: str) -> None:
    _openssl(
        "req",
        "-x509",
        "-new",
        "-key",
        str(key),
        "-sha256",
        "-days",
        "3650",
        "-subj",
        f"/CN={common_name}",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        "-out",
        str(certificate),
    )


def _sign(
    request: Path,
    ca_certificate: Path,
    ca_key: Path,
    certificate: Path,
    *,
    days: int = 90,
    extensions: str | None = None,
) -> None:
    arguments = [
        "x509",
        "-req",
        "-in",
        str(request),
        "-CA",
        str(ca_certificate),
        "-CAkey",
        str(ca_key),
        "-CAcreateserial",
        "-days",
        str(days),
        "-sha256",
        "-out",
        str(certificate),
    ]
    if extensions is not None:
        extension_file = certificate.with_suffix(".ext")
        extension_file.write_text(extensions + "\n", encoding="ascii")
        arguments += ["-extfile", str(extension_file)]
    _openssl(*arguments)


def _sign_expired(
    request: Path,
    ca_certificate: Path,
    ca_key: Path,
    certificate: Path,
    *,
    extensions: str,
    directory: Path,
) -> None:
    """`openssl x509 -req` cannot backdate a certificate; `openssl ca` can."""
    database = directory / "expired-db"
    (database / "newcerts").mkdir(parents=True)
    (database / "index.txt").touch()
    (database / "serial").write_text("1000\n", encoding="ascii")
    configuration = directory / "expired-ca.cnf"
    configuration.write_text(
        "[ ca ]\n"
        "default_ca = CA_default\n"
        "[ CA_default ]\n"
        f"dir = {database}\n"
        "database = $dir/index.txt\n"
        "new_certs_dir = $dir/newcerts\n"
        f"certificate = {ca_certificate}\n"
        f"private_key = {ca_key}\n"
        "serial = $dir/serial\n"
        "default_md = sha256\n"
        "policy = policy_any\n"
        "email_in_dn = no\n"
        "rand_serial = no\n"
        "unique_subject = no\n"
        "x509_extensions = leaf_ext\n"
        "[ policy_any ]\n"
        "commonName = optional\n"
        "[ leaf_ext ]\n"
        f"{extensions}\n",
        encoding="ascii",
    )
    _openssl(
        "ca",
        "-batch",
        "-notext",
        "-config",
        str(configuration),
        "-in",
        str(request),
        "-startdate",
        "20200101000000Z",
        "-enddate",
        "20200102000000Z",
        "-out",
        str(certificate),
    )


@pytest.fixture(scope="session", autouse=True)
def require_openssl_three() -> None:
    binary = shutil.which("openssl")
    if binary is None:
        pytest.skip("OpenSSL is not installed")
    version = subprocess.run(  # noqa: S603 - fixed binary, no shell
        [binary, "version"], capture_output=True, text=True, check=False, timeout=30
    )
    if not re.search(r"OpenSSL [3-9]\.", version.stdout):
        pytest.skip(f"OpenSSL 3.x is required; found {version.stdout.strip()}")


@pytest.fixture(scope="session")
def pki(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Pki]:
    directory = tmp_path_factory.mktemp("charsooq-tls-pki")

    root_key = directory / "root.key"
    root_cert = directory / "root.crt"
    _generate_key(root_key)
    _self_signed_ca(root_cert, root_key, "Charsooq Test Root CA")

    intermediate_key = directory / "intermediate.key"
    intermediate_cert = directory / "intermediate.crt"
    _generate_key(intermediate_key)
    _sign(
        _generate_csr(intermediate_key, "Charsooq Test Intermediate CA"),
        root_cert,
        root_key,
        intermediate_cert,
        days=365,
        extensions="basicConstraints=critical,CA:TRUE,pathlen:0\n"
        "keyUsage=critical,keyCertSign,cRLSign",
    )

    leaf_key = directory / "leaf.key"
    leaf_cert = directory / "leaf.crt"
    _generate_key(leaf_key)
    _sign(
        _generate_csr(leaf_key, "charsooq.example.test"),
        intermediate_cert,
        intermediate_key,
        leaf_cert,
        extensions="subjectAltName=DNS:charsooq.example.test,DNS:*.apps.example.test,"
        "IP:192.0.2.10\n"
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth",
    )
    leaf_fullchain = directory / "fullchain.pem"
    leaf_fullchain.write_text(
        leaf_cert.read_text(encoding="ascii") + intermediate_cert.read_text(encoding="ascii"),
        encoding="ascii",
    )

    direct_leaf_key = directory / "direct-leaf.key"
    direct_leaf_cert = directory / "direct-leaf.crt"
    _generate_key(direct_leaf_key)
    _sign(
        _generate_csr(direct_leaf_key, "direct.example.test"),
        root_cert,
        root_key,
        direct_leaf_cert,
        extensions="subjectAltName=DNS:direct.example.test\n"
        "basicConstraints=critical,CA:FALSE\n"
        "extendedKeyUsage=serverAuth",
    )

    wrong_host_key = directory / "wrong-host.key"
    wrong_host_cert = directory / "wrong-host.crt"
    _generate_key(wrong_host_key)
    _sign(
        _generate_csr(wrong_host_key, "wrong.example.test"),
        intermediate_cert,
        intermediate_key,
        wrong_host_cert,
        extensions="subjectAltName=DNS:wrong.example.test",
    )

    no_san_key = directory / "no-san.key"
    no_san_cert = directory / "no-san.crt"
    _generate_key(no_san_key)
    _sign(
        _generate_csr(no_san_key, "no-san.example.test"),
        intermediate_cert,
        intermediate_key,
        no_san_cert,
        extensions="basicConstraints=critical,CA:FALSE",
    )

    expired_key = directory / "expired.key"
    expired_cert = directory / "expired.crt"
    _generate_key(expired_key)
    _sign_expired(
        _generate_csr(expired_key, "expired.example.test"),
        root_cert,
        root_key,
        expired_cert,
        extensions="subjectAltName=DNS:expired.example.test",
        directory=directory,
    )

    other_key = directory / "other.key"
    _generate_key(other_key)

    wrong_host_fullchain = directory / "wrong-host-fullchain.pem"
    wrong_host_fullchain.write_text(
        wrong_host_cert.read_text(encoding="ascii") + intermediate_cert.read_text(encoding="ascii"),
        encoding="ascii",
    )
    no_san_fullchain = directory / "no-san-fullchain.pem"
    no_san_fullchain.write_text(
        no_san_cert.read_text(encoding="ascii") + intermediate_cert.read_text(encoding="ascii"),
        encoding="ascii",
    )

    yield Pki(
        root_cert=root_cert,
        root_key=root_key,
        intermediate_cert=intermediate_cert,
        intermediate_key=intermediate_key,
        leaf_cert=leaf_cert,
        leaf_key=leaf_key,
        leaf_fullchain=leaf_fullchain,
        direct_leaf_cert=direct_leaf_cert,
        direct_leaf_key=direct_leaf_key,
        wrong_host_cert=wrong_host_cert,
        wrong_host_key=wrong_host_key,
        wrong_host_fullchain=wrong_host_fullchain,
        no_san_cert=no_san_cert,
        no_san_key=no_san_key,
        no_san_fullchain=no_san_fullchain,
        expired_cert=expired_cert,
        expired_key=expired_key,
        other_key=other_key,
    )
    shutil.rmtree(directory, ignore_errors=True)


def _tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and script, no shell
        [sys.executable, str(TOOL), *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _activate(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and script, no shell
        [sys.executable, str(ACTIVATE_TOOL), *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _assert_fails(result: subprocess.CompletedProcess[str], expected: str) -> None:
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert expected.lower() in output.lower(), output


def test_valid_fullchain_passes_without_printing_key_material(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.leaf_fullchain),
        "--key",
        str(pki.leaf_key),
        "--host",
        "charsooq.example.test",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout
    assert "PRIVATE KEY" not in result.stdout + result.stderr
    # The chain-only run is explicit about verifying structure, not trust roots.
    assert "structure only" in result.stdout


def test_fullchain_verified_against_an_explicit_trust_anchor(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.leaf_fullchain),
        "--key",
        str(pki.leaf_key),
        "--host",
        "charsooq.example.test",
        "--ca-file",
        str(pki.root_cert),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout
    assert "structure only" not in result.stdout


def test_leaf_signed_directly_by_the_root_needs_no_intermediate(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.direct_leaf_cert),
        "--key",
        str(pki.direct_leaf_key),
        "--host",
        "direct.example.test",
        "--ca-file",
        str(pki.root_cert),
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_leaf_without_intermediates_is_rejected(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.leaf_cert),
        "--key",
        str(pki.leaf_key),
        "--host",
        "charsooq.example.test",
    )

    _assert_fails(result, "contains only the leaf")


def test_missing_intermediate_is_rejected(pki: Pki) -> None:
    incomplete = pki.leaf_fullchain.with_name("incomplete.pem")
    incomplete.write_text(
        pki.leaf_cert.read_text(encoding="ascii") + pki.root_cert.read_text(encoding="ascii"),
        encoding="ascii",
    )

    result = _tool(
        "--cert",
        str(incomplete),
        "--key",
        str(pki.leaf_key),
        "--host",
        "charsooq.example.test",
        "--ca-file",
        str(pki.root_cert),
    )

    _assert_fails(result, "incomplete or out of order")


def test_reversed_chain_is_rejected(pki: Pki) -> None:
    reversed_chain = pki.leaf_fullchain.with_name("reversed.pem")
    reversed_chain.write_text(
        pki.intermediate_cert.read_text(encoding="ascii")
        + pki.leaf_cert.read_text(encoding="ascii"),
        encoding="ascii",
    )

    result = _tool(
        "--cert",
        str(reversed_chain),
        "--key",
        str(pki.intermediate_key),
        "--host",
        "charsooq.example.test",
        "--ca-file",
        str(pki.root_cert),
    )

    _assert_fails(result, "incomplete or out of order")


def test_mismatched_private_key_is_rejected(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.leaf_fullchain),
        "--key",
        str(pki.other_key),
        "--host",
        "charsooq.example.test",
    )

    _assert_fails(result, "does not match")


def test_host_outside_the_san_is_rejected(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.wrong_host_fullchain),
        "--key",
        str(pki.wrong_host_key),
        "--host",
        "charsooq.example.test",
        "--ca-file",
        str(pki.root_cert),
    )

    _assert_fails(result, "does not cover")


def test_certificate_without_san_is_rejected(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.no_san_fullchain),
        "--key",
        str(pki.no_san_key),
        "--host",
        "no-san.example.test",
        "--ca-file",
        str(pki.root_cert),
    )

    _assert_fails(result, "does not cover")


def test_wildcard_san_matches_exactly_one_label(pki: Pki) -> None:
    matches = _tool(
        "--cert",
        str(pki.leaf_fullchain),
        "--key",
        str(pki.leaf_key),
        "--host",
        "panel.apps.example.test",
        "--ca-file",
        str(pki.root_cert),
    )
    assert matches.returncode == 0, matches.stdout + matches.stderr

    too_deep = _tool(
        "--cert",
        str(pki.leaf_fullchain),
        "--key",
        str(pki.leaf_key),
        "--host",
        "a.b.apps.example.test",
        "--ca-file",
        str(pki.root_cert),
    )
    _assert_fails(too_deep, "does not cover")


def test_ip_san_matches_the_literal_address(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.leaf_fullchain),
        "--key",
        str(pki.leaf_key),
        "--host",
        "192.0.2.10",
        "--ca-file",
        str(pki.root_cert),
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_expired_certificate_is_rejected(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.expired_cert),
        "--key",
        str(pki.expired_key),
        "--host",
        "expired.example.test",
        "--ca-file",
        str(pki.root_cert),
    )

    _assert_fails(result, "expired")


def test_remaining_lifetime_threshold_is_enforced(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.leaf_fullchain),
        "--key",
        str(pki.leaf_key),
        "--host",
        "charsooq.example.test",
        "--ca-file",
        str(pki.root_cert),
        "--min-remaining-days",
        "365",
    )

    _assert_fails(result, "below the 365-day threshold")


def test_missing_certificate_is_rejected(pki: Pki) -> None:
    result = _tool(
        "--cert",
        str(pki.leaf_fullchain.with_name("absent.pem")),
        "--key",
        str(pki.leaf_key),
        "--host",
        "charsooq.example.test",
    )

    _assert_fails(result, "does not exist")


def test_empty_certificate_is_rejected(pki: Pki) -> None:
    empty = pki.leaf_fullchain.with_name("empty.pem")
    empty.write_bytes(b"")

    result = _tool(
        "--cert",
        str(empty),
        "--key",
        str(pki.leaf_key),
        "--host",
        "charsooq.example.test",
    )

    _assert_fails(result, "empty")


def test_non_pem_certificate_is_rejected(pki: Pki) -> None:
    garbage = pki.leaf_fullchain.with_name("garbage.pem")
    garbage.write_text("not a certificate\n", encoding="ascii")

    result = _tool(
        "--cert",
        str(garbage),
        "--key",
        str(pki.leaf_key),
        "--host",
        "charsooq.example.test",
    )

    _assert_fails(result, "no PEM certificate")


def test_world_readable_private_key_is_rejected(pki: Pki) -> None:
    loose = pki.leaf_fullchain.with_name("loose.key")
    shutil.copyfile(pki.leaf_key, loose)
    loose.chmod(0o644)

    result = _tool(
        "--cert",
        str(pki.leaf_fullchain),
        "--key",
        str(loose),
        "--host",
        "charsooq.example.test",
    )

    _assert_fails(result, "other users")


def test_group_readable_private_key_passes_with_a_warning(pki: Pki) -> None:
    shared = pki.leaf_fullchain.with_name("shared.key")
    shutil.copyfile(pki.leaf_key, shared)
    shared.chmod(0o640)

    result = _tool(
        "--cert",
        str(pki.leaf_fullchain),
        "--key",
        str(shared),
        "--host",
        "charsooq.example.test",
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "group access" in output


def test_certificate_material_is_git_ignored_and_untracked() -> None:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not installed")

    tracked = subprocess.run(  # noqa: S603 - fixed binary, no shell
        [git, "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    committed = [
        path for path in tracked.stdout.splitlines() if path.lower().endswith(CERT_EXTENSIONS)
    ]
    assert committed == []

    ignored = subprocess.run(  # noqa: S603 - fixed binary, no shell
        [
            git,
            "-C",
            str(REPO_ROOT),
            "check-ignore",
            "--no-index",
            "deploy/tls/fullchain.pem",
            "deploy/tls/privkey.key",
            "deploy/tls/org-root.crt",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert ignored.returncode == 0
    assert len(ignored.stdout.splitlines()) == 3

    for path in (REPO_ROOT / "deploy").rglob("*"):
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="ignore")
            assert PEM_BODY.search(content) is None, f"{path} contains PEM material"


def test_docker_build_context_excludes_tls_material_and_tooling() -> None:
    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    entries = {
        line.strip()
        for line in dockerignore.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "deploy" in entries
    for pattern in ("**/*.pem", "**/*.key", "**/*.crt", "**/*.p12", "**/*.pfx"):
        assert pattern in entries

    for dockerfile in ("Dockerfile.api", "Dockerfile.web"):
        content = (REPO_ROOT / dockerfile).read_text(encoding="utf-8")
        assert "COPY deploy" not in content
        assert "etc/charsooq" not in content


def test_only_the_proxy_receives_certificate_mounts_and_ca_state() -> None:
    compose = cast(dict[str, Any], yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8")))
    services = compose["services"]

    caddy_volumes = [str(volume) for volume in services["caddy"]["volumes"]]
    assert any(volume.endswith(":/etc/caddy/certs:ro") for volume in caddy_volumes)
    assert any(str(volume).startswith("caddy_data:/data") for volume in caddy_volumes)
    assert any(str(volume).startswith("caddy_config:/config") for volume in caddy_volumes)
    assert "secrets" not in services["caddy"]
    assert set(services["caddy"]["environment"]) == {
        "CHARSOOQ_SITE_HOST",
        "CHARSOOQ_TLS_MODE",
        "CHARSOOQ_HSTS_MAX_AGE",
    }

    for name, service in services.items():
        if name == "caddy":
            continue
        mounts = [str(volume) for volume in service.get("volumes", [])]
        assert not any("caddy" in mount or "/certs" in mount for mount in mounts), name


def _tls_directory(tmp_path: Path) -> Path:
    directory = tmp_path / "tls"
    directory.mkdir(mode=0o700)
    return directory


def _install(
    pki: Pki,
    tls_dir: Path,
    stamp: str,
    *,
    cert: Path | None = None,
    key: Path | None = None,
    host: str = "charsooq.example.test",
) -> subprocess.CompletedProcess[str]:
    return _activate(
        "--tls-dir",
        str(tls_dir),
        "--cert",
        str(cert or pki.leaf_fullchain),
        "--key",
        str(key or pki.leaf_key),
        "--host",
        host,
        "--ca-file",
        str(pki.root_cert),
        "--stamp",
        stamp,
    )


def test_activation_switches_one_symlink_to_a_complete_validated_pair(
    pki: Pki, tmp_path: Path
) -> None:
    tls_dir = _tls_directory(tmp_path)

    result = _install(pki, tls_dir, "v1")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    current = tls_dir / "current"
    assert current.is_symlink()
    assert os.readlink(current) == "versions/v1"
    assert (current / "fullchain.pem").read_text(encoding="ascii") == pki.leaf_fullchain.read_text(
        encoding="ascii"
    )
    assert (current / "privkey.pem").read_bytes() == pki.leaf_key.read_bytes()
    assert stat.S_IMODE((current / "fullchain.pem").stat().st_mode) == 0o644
    assert stat.S_IMODE((current / "privkey.pem").stat().st_mode) == 0o600
    assert "restart" in output.lower()
    assert "PRIVATE KEY" not in output


def test_activation_rejects_a_mismatched_pair_and_keeps_the_previous_version(
    pki: Pki, tmp_path: Path
) -> None:
    tls_dir = _tls_directory(tmp_path)
    assert _install(pki, tls_dir, "v1").returncode == 0

    result = _install(pki, tls_dir, "v2", key=pki.other_key)

    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "does not match" in output
    assert os.readlink(tls_dir / "current") == "versions/v1"
    assert not (tls_dir / "versions" / "v2").exists()


def test_activation_rejects_a_wrong_host_without_creating_current(pki: Pki, tmp_path: Path) -> None:
    tls_dir = _tls_directory(tmp_path)

    result = _install(pki, tls_dir, "v1", host="other.example.test")

    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "does not cover" in output
    assert not os.path.lexists(tls_dir / "current")
    assert not (tls_dir / "versions" / "v1").exists()


def test_rotation_keeps_both_versions_and_rollback_switches_back(pki: Pki, tmp_path: Path) -> None:
    tls_dir = _tls_directory(tmp_path)
    assert _install(pki, tls_dir, "v1").returncode == 0
    assert _install(pki, tls_dir, "v2").returncode == 0
    assert os.readlink(tls_dir / "current") == "versions/v2"

    rollback = _activate(
        "--tls-dir",
        str(tls_dir),
        "--rollback-to",
        "v1",
        "--host",
        "charsooq.example.test",
        "--ca-file",
        str(pki.root_cert),
    )

    output = rollback.stdout + rollback.stderr
    assert rollback.returncode == 0, output
    assert os.readlink(tls_dir / "current") == "versions/v1"
    assert (tls_dir / "versions" / "v2" / "fullchain.pem").is_file()
    assert "versions/v2" in output


def test_rollback_to_a_missing_version_changes_nothing(pki: Pki, tmp_path: Path) -> None:
    tls_dir = _tls_directory(tmp_path)
    assert _install(pki, tls_dir, "v1").returncode == 0

    result = _activate(
        "--tls-dir",
        str(tls_dir),
        "--rollback-to",
        "v9",
        "--host",
        "charsooq.example.test",
        "--ca-file",
        str(pki.root_cert),
    )

    assert result.returncode == 1
    assert os.readlink(tls_dir / "current") == "versions/v1"


def test_activation_normalises_source_permissions(pki: Pki, tmp_path: Path) -> None:
    tls_dir = _tls_directory(tmp_path)
    loose_source = tmp_path / "loose-source.key"
    shutil.copyfile(pki.leaf_key, loose_source)
    loose_source.chmod(0o644)

    result = _install(pki, tls_dir, "v1", key=loose_source)

    assert result.returncode == 0, result.stdout + result.stderr
    assert stat.S_IMODE((tls_dir / "versions/v1/privkey.pem").stat().st_mode) == 0o600


def test_activation_refuses_to_replace_a_real_current_directory(pki: Pki, tmp_path: Path) -> None:
    tls_dir = _tls_directory(tmp_path)
    (tls_dir / "current").mkdir()

    result = _install(pki, tls_dir, "v1")

    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "not a symlink" in output
    assert (tls_dir / "current").is_dir()
    assert not (tls_dir / "versions" / "v1").exists()
