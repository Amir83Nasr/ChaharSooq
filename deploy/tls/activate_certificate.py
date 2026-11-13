#!/usr/bin/env python3
"""Validate and atomically activate a certificate pair for the Caddy container.

Layout inside the directory mounted at ``/etc/caddy/certs``::

    current -> versions/<stamp>       the only pointer Caddy reads through
    versions/<stamp>/fullchain.pem    leaf first, then intermediates, 0644
    versions/<stamp>/privkey.pem      matching key, 0600

The certificate and key are copied into a new version directory, validated
there (the same checks as ``validate_certificate.py``), and only then made
active by replacing the single ``current`` symlink with ``os.replace``. That
rename is atomic, so the proxy can never start from a half-switched pair. A
failure leaves the previously active version untouched.

The tool does not restart Caddy and does not use the admin API (``admin off``).
Restart the proxy after a successful activation. It never prints key material,
never contacts the network, and never issues or renews a certificate.

Usage::

    # Install and activate new material (usually with sudo).
    activate_certificate.py --tls-dir /etc/charsooq/tls \
        --cert /root/incoming/fullchain.pem \
        --key /root/incoming/privkey.pem \
        --host charsooq.example.test \
        --ca-file /etc/charsooq/tls/org-root.crt

    # Roll back to a version that is still on the host.
    activate_certificate.py --tls-dir /etc/charsooq/tls \
        --rollback-to 20261101T090000Z \
        --host charsooq.example.test \
        --ca-file /etc/charsooq/tls/org-root.crt

Exit status: 0 = activated, 1 = validation or activation failed, 2 = usage.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

VALIDATE_TOOL = Path(__file__).resolve().with_name("validate_certificate.py")
STAMP_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CERT_NAME = "fullchain.pem"
KEY_NAME = "privkey.pem"


class ActivationError(Exception):
    """A failure with a message safe to print."""


def _check_stamp(stamp: str) -> str:
    if not STAMP_PATTERN.match(stamp) or ".." in stamp:
        raise ActivationError(f"invalid version name: {stamp!r}")
    return stamp


def _validate_pair(
    cert: Path, key: Path, host: str, ca_file: Path | None, min_days: int
) -> None:
    command = [
        sys.executable,
        str(VALIDATE_TOOL),
        "--cert",
        str(cert),
        "--key",
        str(key),
        "--host",
        host,
        "--min-remaining-days",
        str(min_days),
    ]
    if ca_file is not None:
        command += ["--ca-file", str(ca_file)]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise ActivationError(
            "certificate validation failed; the active pair was not changed"
        )


def _current_target(tls_dir: Path) -> str | None:
    current = tls_dir / "current"
    if not os.path.lexists(current):
        return None
    if not current.is_symlink():
        raise ActivationError(
            f"{current} exists and is not a symlink; refusing to replace it"
        )
    return os.readlink(current)


def _switch_current(tls_dir: Path, stamp: str) -> str | None:
    version_dir = tls_dir / "versions" / stamp
    if not version_dir.is_dir():
        raise ActivationError(f"version directory does not exist: {version_dir}")

    previous = _current_target(tls_dir)
    temporary = tls_dir / f".current.{os.getpid()}.tmp"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(Path("versions") / stamp, target_is_directory=True)
    try:
        os.replace(temporary, tls_dir / "current")
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ActivationError(f"cannot replace the current symlink: {exc}") from exc
    return previous


def _restore_current(tls_dir: Path, previous: str | None) -> None:
    current = tls_dir / "current"
    if previous is None:
        current.unlink(missing_ok=True)
        return
    temporary = tls_dir / f".current.{os.getpid()}.restore.tmp"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(previous, target_is_directory=True)
    os.replace(temporary, current)


def _install(
    tls_dir: Path,
    cert: Path,
    key: Path,
    host: str,
    ca_file: Path | None,
    min_days: int,
    stamp: str,
) -> None:
    for path, label in ((cert, "certificate"), (key, "private key")):
        if not path.exists() or not path.is_file():
            raise ActivationError(f"{label} file does not exist: {path}")

    versions = tls_dir / "versions"
    versions.mkdir(mode=0o700, exist_ok=True)
    version_dir = versions / stamp
    if version_dir.exists():
        raise ActivationError(
            f"version {stamp!r} already exists; use another --stamp or leave it to the timestamp"
        )
    version_dir.mkdir(mode=0o700)

    installed_cert = version_dir / CERT_NAME
    installed_key = version_dir / KEY_NAME
    try:
        shutil.copyfile(cert, installed_cert)
        os.chmod(installed_cert, 0o644)
        shutil.copyfile(key, installed_key)
        os.chmod(installed_key, 0o600)
        print(f"staged {installed_cert}")
        print(f"staged {installed_key} (mode 0600)")

        _validate_pair(installed_cert, installed_key, host, ca_file, min_days)
        previous = _switch_current(tls_dir, stamp)
        print(f"activated versions/{stamp}")
        if previous is not None:
            print(f"previous version: {previous}")
    except (ActivationError, OSError) as exc:
        # The new version is never partially active; remove the staged copy so a
        # retry starts clean. The previous version directory is untouched.
        shutil.rmtree(version_dir, ignore_errors=True)
        raise ActivationError(str(exc)) from exc

    try:
        _validate_pair(
            tls_dir / "current" / CERT_NAME,
            tls_dir / "current" / KEY_NAME,
            host,
            ca_file,
            min_days,
        )
    except ActivationError:
        _restore_current(tls_dir, previous)
        raise ActivationError(
            "the pair failed validation through the current symlink; the previous version was restored"
        ) from None


def _rollback(tls_dir: Path, stamp: str, host: str, ca_file: Path | None) -> None:
    version_dir = tls_dir / "versions" / stamp
    if not version_dir.is_dir():
        raise ActivationError(f"version directory does not exist: {version_dir}")
    # A rollback may target a certificate that is close to expiry; structural
    # checks, key match, SAN, and "not expired" still apply.
    _validate_pair(version_dir / CERT_NAME, version_dir / KEY_NAME, host, ca_file, 0)
    previous = _switch_current(tls_dir, stamp)
    print(f"activated versions/{stamp}")
    if previous is not None:
        print(f"previous version: {previous}")


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a certificate/key pair and switch Caddy to it with a single "
            "atomic symlink replacement. Does not restart Caddy."
        )
    )
    parser.add_argument(
        "--tls-dir", required=True, type=Path, help="host TLS directory"
    )
    parser.add_argument("--cert", type=Path, help="staged PEM chain (leaf first)")
    parser.add_argument("--key", type=Path, help="staged PEM private key")
    parser.add_argument(
        "--rollback-to", metavar="STAMP", help="activate an existing version"
    )
    parser.add_argument(
        "--stamp", help="version name for a new install (default: UTC timestamp)"
    )
    parser.add_argument(
        "--host", required=True, help="expected DNS name or literal IP in the leaf SAN"
    )
    parser.add_argument(
        "--ca-file", type=Path, default=None, help="trust anchor for chain validation"
    )
    parser.add_argument(
        "--min-remaining-days",
        type=_positive_int,
        default=30,
        help="reject a new certificate that expires sooner (default: 30; rollback uses 0)",
    )
    arguments = parser.parse_args(argv)

    try:
        tls_dir = arguments.tls_dir
        if not tls_dir.is_dir():
            raise ActivationError(f"TLS directory does not exist: {tls_dir}")
        mode = tls_dir.stat().st_mode & 0o777
        if mode & 0o077:
            print(
                f"warning: {tls_dir} mode is {mode:04o}; 0700 is expected for a key directory",
                file=sys.stderr,
            )

        if arguments.rollback_to is not None:
            if arguments.cert or arguments.key or arguments.stamp:
                raise ActivationError(
                    "--rollback-to cannot be combined with --cert/--key/--stamp"
                )
            _rollback(
                tls_dir,
                _check_stamp(arguments.rollback_to),
                arguments.host,
                arguments.ca_file,
            )
        else:
            if arguments.cert is None or arguments.key is None:
                raise ActivationError(
                    "--cert and --key are required unless --rollback-to is used"
                )
            stamp = _check_stamp(
                arguments.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            )
            _install(
                tls_dir,
                arguments.cert,
                arguments.key,
                arguments.host,
                arguments.ca_file,
                arguments.min_remaining_days,
                stamp,
            )
    except ActivationError as exc:
        print(f"FAIL  {exc}", file=sys.stderr)
        return 1

    print()
    print("The active pair changed. Restart Caddy to load it (admin API is off):")
    print("  docker compose -f compose.production.yml restart caddy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
