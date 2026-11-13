#!/usr/bin/env python3
"""Validate the TLS material mounted into the Caddy container, offline.

Checks, in order:

1. the certificate and key files exist, are readable, and are not empty;
2. the certificate file is a PEM chain whose first certificate is the leaf;
3. the private key parses, is not encrypted, and matches the leaf;
4. the leaf is currently valid and has enough remaining lifetime;
5. the chain is complete, correctly ordered, and every signature verifies
   (with ``--ca-file`` the chain must terminate at that trust anchor);
6. the leaf's SAN covers the expected host, as a DNS name or a literal IP;
7. the private key is not accessible to group/other (group access warns).

The tool never prints private-key material, never connects to the network, and
never issues, renews, or installs a certificate. It is read-only: it does not
write next to the input files (temporary public-certificate copies live in a
private temporary directory and are removed on exit).

Requires OpenSSL 3.x on ``PATH`` (Ubuntu 22.04+ and current macOS Homebrew).

Usage::

    deploy/tls/validate_certificate.py \\
        --cert /etc/charsooq/tls/current/fullchain.pem \\
        --key /etc/charsooq/tls/current/privkey.pem \\
        --host charsooq.example.test \\
        [--ca-file /etc/charsooq/tls/org-root.crt] \\
        [--min-remaining-days 30]

Exit status: 0 = pass, 1 = validation failed, 2 = usage error.
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

CERT_BLOCK = re.compile(
    r"-----BEGIN CERTIFICATE-----\r?\n.+?-----END CERTIFICATE-----",
    re.DOTALL,
)
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?:ENCRYPTED )?(?:RSA |EC |DSA )?PRIVATE KEY-----"
)
SAN_ENTRY = re.compile(r"\b(?P<kind>DNS|IP Address):(?P<value>[^,\n]+)")
OPENSSL_TIMEOUT_SECONDS = 30


class ValidationError(Exception):
    """A validation failure with a message safe to print."""


@dataclass(frozen=True)
class Certificate:
    """The public, non-secret fields of one certificate."""

    pem: str
    subject: str
    issuer: str
    not_before: datetime
    not_after: datetime
    dns_sans: tuple[str, ...]
    ip_sans: tuple[str, ...]


@dataclass
class Report:
    """Collects outcomes so every failure is reported in one run."""

    failures: int = 0
    warnings: int = 0

    def ok(self, message: str) -> None:
        print(f"ok    {message}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"warn  {message}")

    def fail(self, message: str) -> None:
        self.failures += 1
        print(f"FAIL  {message}")


def _openssl(*args: str) -> subprocess.CompletedProcess[str]:
    """Run an OpenSSL subcommand without a shell and without stdin prompts."""
    try:
        return subprocess.run(
            ["openssl", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=OPENSSL_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise ValidationError("openssl was not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValidationError("openssl timed out") from exc


def _require_openssl_three() -> str:
    result = _openssl("version")
    version = result.stdout.strip()
    match = re.search(r"OpenSSL (\d+)\.", version)
    if result.returncode != 0 or match is None or int(match.group(1)) < 3:
        raise ValidationError(
            f"OpenSSL 3.x is required; found {version or 'an unknown version'}"
        )
    return version


def _read_text(path: Path, label: str) -> str:
    if not path.exists():
        raise ValidationError(f"{label} file does not exist: {path}")
    if not path.is_file():
        raise ValidationError(f"{label} path is not a regular file: {path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValidationError(f"{label} file cannot be inspected: {path}") from exc
    if size == 0:
        raise ValidationError(f"{label} file is empty: {path}")
    try:
        return path.read_text(encoding="ascii")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{label} file is not PEM text: {path}") from exc
    except OSError as exc:
        raise ValidationError(f"{label} file cannot be read: {path}") from exc


def _field(output: str, name: str) -> str:
    prefix = f"{name}="
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise ValidationError(f"openssl did not report the certificate {name}")


def _parse_date(value: str) -> datetime:
    value = value.strip()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    for pattern in ("%b %d %H:%M:%S %Y %Z", "%b %d %H:%M:%S %Y"):
        try:
            parsed = datetime.strptime(value, pattern)  # noqa: DTZ007 - OpenSSL prints UTC
        except ValueError:
            continue
        return parsed.replace(tzinfo=UTC)
    raise ValidationError(f"cannot parse certificate date: {value!r}")


def _parse_sans(output: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    dns: list[str] = []
    addresses: list[str] = []
    for match in SAN_ENTRY.finditer(output):
        value = match.group("value").strip()
        if match.group("kind") == "DNS":
            dns.append(value.lower().rstrip("."))
            continue
        try:
            addresses.append(str(ipaddress.ip_address(value)))
        except ValueError as exc:
            raise ValidationError(
                f"certificate has an unparseable IP SAN: {value}"
            ) from exc
    return tuple(dns), tuple(addresses)


def _load_certificates(pem_text: str, directory: Path, label: str) -> list[Certificate]:
    blocks = CERT_BLOCK.findall(pem_text)
    if not blocks:
        raise ValidationError(f"{label} file contains no PEM certificate")

    certificates: list[Certificate] = []
    for index, block in enumerate(blocks):
        path = directory / f"{label}-{index}.pem"
        path.write_text(block + "\n", encoding="ascii")
        info = _openssl(
            "x509",
            "-in",
            str(path),
            "-noout",
            "-subject",
            "-issuer",
            "-dates",
            "-dateopt",
            "iso_8601",
        )
        if info.returncode != 0:
            raise ValidationError(
                f"{label} certificate {index + 1} cannot be parsed: {info.stderr.strip()}"
            )
        san = _openssl("x509", "-in", str(path), "-noout", "-ext", "subjectAltName")
        if san.returncode != 0:
            raise ValidationError(
                f"{label} certificate {index + 1} SAN cannot be read: {san.stderr.strip()}"
            )
        dns_sans, ip_sans = _parse_sans(san.stdout)
        certificates.append(
            Certificate(
                pem=block,
                subject=_field(info.stdout, "subject"),
                issuer=_field(info.stdout, "issuer"),
                not_before=_parse_date(_field(info.stdout, "notBefore")),
                not_after=_parse_date(_field(info.stdout, "notAfter")),
                dns_sans=dns_sans,
                ip_sans=ip_sans,
            )
        )
    return certificates


def _normalise_pem(pem: str) -> str:
    return "\n".join(line.strip() for line in pem.strip().splitlines() if line.strip())


def _dns_matches(pattern: str, host: str) -> bool:
    if pattern == host:
        return True
    if not pattern.startswith("*.") or "*" in pattern[2:] or not pattern[2:]:
        return False
    _label, _, remainder = host.partition(".")
    return bool(_label) and remainder == pattern[2:]


def _host_is_covered(
    host: str,
    certificate: Certificate,
) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        name = host.lower().rstrip(".")
        return any(_dns_matches(pattern, name) for pattern in certificate.dns_sans)
    return any(ipaddress.ip_address(value) == address for value in certificate.ip_sans)


def _key_mode_problem(mode: int) -> str | None:
    if mode & 0o007:
        return f"private key mode is {mode:04o}: readable or writable by other users"
    if mode & 0o070:
        return (
            f"private key mode is {mode:04o}: group access is allowed; "
            "keep it to the group that the Caddy container actually uses"
        )
    return None


def _load_private_key(path: Path, report: Report) -> str:
    pem_text = _read_text(path, "private key")
    if "-----BEGIN ENCRYPTED PRIVATE KEY-----" in pem_text:
        raise ValidationError(
            "the private key is encrypted; Caddy's file loader cannot prompt for a passphrase"
        )
    if not PRIVATE_KEY_BLOCK.search(pem_text):
        raise ValidationError("the private key file contains no PEM private key")
    # `pkey` only parses; it never prints the key here.
    parsed = _openssl("pkey", "-in", str(path), "-noout", "-passin", "pass:")
    if parsed.returncode != 0:
        raise ValidationError(
            f"the private key cannot be parsed: {parsed.stderr.strip()}"
        )

    mode = stat.S_IMODE(path.stat().st_mode)
    problem = _key_mode_problem(mode)
    if problem is not None:
        if mode & 0o007:
            raise ValidationError(problem)
        report.warn(problem)
    else:
        report.ok(f"private key permissions {mode:04o} (owner-only)")
    return pem_text


def _check_expiry(
    certificate: Certificate, min_remaining_days: int, report: Report
) -> None:
    now = datetime.now(UTC)
    if certificate.not_before > now:
        raise ValidationError(
            f"the leaf certificate is not valid yet (notBefore {certificate.not_before.isoformat()})"
        )
    remaining = (certificate.not_after - now).total_seconds() / 86400
    if remaining <= 0:
        raise ValidationError(
            f"the leaf certificate expired {-remaining:.1f} days ago "
            f"(notAfter {certificate.not_after.isoformat()})"
        )
    if remaining < min_remaining_days:
        raise ValidationError(
            f"the leaf certificate expires in {remaining:.1f} days, below the "
            f"{min_remaining_days}-day threshold (notAfter {certificate.not_after.isoformat()})"
        )
    report.ok(
        f"leaf certificate valid for {remaining:.1f} more days "
        f"(notAfter {certificate.not_after.isoformat()})"
    )


def _verify_chain(
    certificates: Sequence[Certificate],
    ca_certificates: Sequence[Certificate] | None,
    directory: Path,
    report: Report,
) -> None:
    leaf = certificates[0]
    for index in range(len(certificates) - 1):
        current = certificates[index]
        parent = certificates[index + 1]
        if current.issuer != parent.subject:
            raise ValidationError(
                f"certificate {index + 1} is issued by {current.issuer!r} but certificate "
                f"{index + 2} is {parent.subject!r}; the chain is incomplete or out of order"
            )

    if ca_certificates is None:
        if len(certificates) < 2:
            raise ValidationError(
                "the certificate file contains only the leaf; provide the issuing "
                "intermediates in fullchain.pem or pass --ca-file"
            )
        anchor_certificates = [certificates[-1]]
        untrusted = list(certificates[1:-1])
        anchor_note = "the last certificate in the file (structure only)"
        partial_chain = True
    else:
        anchor_certificates = list(ca_certificates)
        untrusted = list(certificates[1:])
        anchor_note = "--ca-file"
        partial_chain = False

    anchor_path = directory / "anchor.pem"
    anchor_path.write_text(
        "\n".join(certificate.pem for certificate in anchor_certificates) + "\n",
        encoding="ascii",
    )
    verify_args = ["verify", "-CAfile", str(anchor_path)]
    if partial_chain:
        # Without a trust anchor from the organization, the last certificate in
        # the file is trusted only for structure: signature and validity.
        verify_args.append("-partial_chain")
    if untrusted:
        untrusted_path = directory / "untrusted.pem"
        untrusted_path.write_text(
            "\n".join(certificate.pem for certificate in untrusted) + "\n",
            encoding="ascii",
        )
        verify_args += ["-untrusted", str(untrusted_path)]
    verify_args.append(str(directory / "certificate-0.pem"))
    verified = _openssl(*verify_args)
    if verified.returncode != 0:
        detail = [line for line in verified.stderr.splitlines() if line.strip()]
        reason = next(
            (line for line in detail if "depth lookup" in line),
            detail[-1] if detail else "no detail",
        )
        raise ValidationError(
            f"chain verification failed against {anchor_note}: {reason}"
        )
    report.ok(
        f"chain: {len(certificates)} certificate(s), leaf issued by {leaf.issuer!r}, "
        f"verified against {anchor_note}"
    )
    if ca_certificates is None:
        report.warn(
            "the chain was verified only against the last certificate in the file; "
            "pass --ca-file with the organization root to verify the trust anchor"
        )


def validate(
    cert_path: Path,
    key_path: Path,
    host: str,
    ca_path: Path | None,
    min_remaining_days: int,
) -> int:
    report = Report()
    print("TLS material validation")
    print(f"  certificate: {cert_path}")
    print(f"  private key: {key_path}")
    print(f"  expected host: {host}")
    print()

    with tempfile.TemporaryDirectory(prefix="charsooq-tls-validate-") as temporary:
        directory = Path(temporary)
        try:
            _require_openssl_three()
            cert_text = _read_text(cert_path, "certificate")
            certificates = _load_certificates(cert_text, directory, "certificate")
            report.ok(
                f"certificate file parsed: {len(certificates)} PEM certificate(s), "
                f"leaf subject {certificates[0].subject!r}"
            )

            _load_private_key(key_path, report)
            leaf_path = directory / "certificate-0.pem"
            cert_public = _openssl("x509", "-in", str(leaf_path), "-noout", "-pubkey")
            key_public = _openssl(
                "pkey", "-in", str(key_path), "-pubout", "-passin", "pass:"
            )
            if cert_public.returncode != 0 or key_public.returncode != 0:
                raise ValidationError(
                    "the public keys of certificate and key cannot be read"
                )
            if _normalise_pem(cert_public.stdout) != _normalise_pem(key_public.stdout):
                raise ValidationError(
                    "the private key does not match the leaf certificate"
                )
            report.ok("private key matches the leaf certificate")

            _check_expiry(certificates[0], min_remaining_days, report)

            ca_certificates: list[Certificate] | None = None
            if ca_path is not None:
                ca_text = _read_text(ca_path, "CA")
                ca_certificates = _load_certificates(ca_text, directory, "ca")
            _verify_chain(certificates, ca_certificates, directory, report)

            if not _host_is_covered(host, certificates[0]):
                expected = host.strip()
                found = ", ".join([*certificates[0].dns_sans, *certificates[0].ip_sans])
                raise ValidationError(
                    f"the leaf certificate does not cover {expected!r}; SANs: {found or 'none'}"
                )
            report.ok(f"leaf SAN covers {host!r}")
        except ValidationError as exc:
            report.fail(str(exc))

    print()
    if report.failures:
        print(
            f"RESULT: FAIL ({report.failures} failure(s), {report.warnings} warning(s))"
        )
        return 1
    print(f"RESULT: PASS ({report.warnings} warning(s))")
    return 0


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
            "Validate a certificate chain and private key offline, without printing "
            "key material, issuing certificates, or contacting the network."
        )
    )
    parser.add_argument(
        "--cert", required=True, type=Path, help="PEM chain, leaf first"
    )
    parser.add_argument(
        "--key", required=True, type=Path, help="matching PEM private key"
    )
    parser.add_argument(
        "--host",
        required=True,
        help="expected DNS name or literal IP; must appear in the leaf SAN",
    )
    parser.add_argument(
        "--ca-file",
        type=Path,
        default=None,
        help="organization trust anchor (root CA) used to verify the full chain",
    )
    parser.add_argument(
        "--min-remaining-days",
        type=_positive_int,
        default=30,
        help="fail when the leaf expires sooner than this many days (default: 30)",
    )
    arguments = parser.parse_args(argv)
    return validate(
        cert_path=arguments.cert,
        key_path=arguments.key,
        host=arguments.host,
        ca_path=arguments.ca_file,
        min_remaining_days=arguments.min_remaining_days,
    )


if __name__ == "__main__":
    sys.exit(main())
