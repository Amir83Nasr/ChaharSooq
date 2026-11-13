"""Caddy configuration invariants for the internal reverse proxy.

These tests read the committed snippets only. They do not need Docker, TLS
material, a DNS name, or any real secret.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
CADDY_DIR = REPO_ROOT / "deploy" / "caddy"
COMPOSE_PATH = REPO_ROOT / "compose.production.yml"


def _read(name: str) -> str:
    return (CADDY_DIR / name).read_text(encoding="utf-8")


def _code(name: str) -> str:
    """Directives only: full-line comments explain the decisions, so they must
    not make a forbidden-directive assertion pass or fail."""
    lines = [line for line in _read(name).splitlines() if not line.lstrip().startswith("#")]
    return "\n".join(lines)


def _compose() -> dict[str, Any]:
    with COMPOSE_PATH.open(encoding="utf-8") as handle:
        return cast(dict[str, Any], yaml.safe_load(handle))


def test_the_only_upstream_is_the_web_container() -> None:
    site = _code("site.caddy")

    assert site.count("reverse_proxy") == 1
    assert "reverse_proxy web:3000" in site
    assert "api:8000" not in site
    assert "db:5432" not in site
    assert "provision" not in site
    assert "migrate" not in site


def test_https_is_the_only_site_scheme_and_tls_mode_is_selected() -> None:
    root = _code("Caddyfile")

    assert "https://{$CHARSOOQ_SITE_HOST}" in root
    # There is no http:// site block, so a plain-HTTP Production cannot be
    # configured by accident; automatic HTTPS creates the :80 redirect.
    assert "http://" not in root
    assert "import tls-{$CHARSOOQ_TLS_MODE}.caddy" in root
    assert "admin off" in root
    assert "skip_install_trust" in root

    assert (CADDY_DIR / "tls-organization.caddy").is_file()
    assert (CADDY_DIR / "tls-internal-ca.caddy").is_file()
    assert "tls internal" in _code("tls-internal-ca.caddy")
    assert "fullchain.pem" in _code("tls-organization.caddy")


def test_client_forwarding_headers_are_overwritten_not_trusted() -> None:
    site = _code("site.caddy")

    for header, placeholder in (
        ("X-Forwarded-For", "{remote_host}"),
        ("X-Forwarded-Proto", "{scheme}"),
        ("X-Forwarded-Host", "{host}"),
        ("X-Forwarded-Port", "443"),
    ):
        assert f"header_up {header} {placeholder}" in site
    # RFC 7239 and vendor headers Caddy would otherwise pass through untouched.
    for header in ("-Forwarded", "-X-Real-IP", "-X-Forwarded-Server"):
        assert f"header_up {header}" in site
    # Nothing upstream of Caddy is trusted, so no XFF value is ever accepted.
    assert "trusted_proxies" not in site


def test_hsts_is_owned_here_and_stays_conservative() -> None:
    site = _code("site.caddy")

    assert 'Strict-Transport-Security "max-age=31536000"' in site
    # includeSubDomains/preload wait for the DNS and TLS decisions owned by IT.
    assert "includeSubDomains" not in site
    assert "preload" not in site


def test_no_certificate_material_or_private_key_is_committed() -> None:
    files = sorted(path.name for path in CADDY_DIR.rglob("*") if path.is_file())

    assert all(name.endswith(".caddy") or name == "Caddyfile" for name in files)
    assert "docker.sock" not in "".join(_read(name) for name in files)


def test_organization_tls_defaults_to_the_container_mount_and_is_overridable() -> None:
    tls = _code("tls-organization.caddy")

    assert "{$CHARSOOQ_TLS_CERT_FILE:/etc/caddy/certs/current/fullchain.pem}" in tls
    assert "{$CHARSOOQ_TLS_KEY_FILE:/etc/caddy/certs/current/privkey.pem}" in tls


def test_http3_is_not_advertised() -> None:
    # compose publishes TCP 80/443 only; an alt-svc h3 advertisement would point
    # clients at a UDP port nothing listens on.
    assert "protocols h1 h2" in _code("Caddyfile")


def test_access_log_never_captures_credentials() -> None:
    """Caddy logs request headers by default but excludes Cookie, Set-Cookie,
    Authorization, and Proxy-Authorization unless `log_credentials` is enabled.
    No snippet may enable it or inject those headers into the log format."""

    forbidden = (
        "log_credentials",
        "cookie",
        "authorization",
        "request>headers",
        "http.request.header",
    )
    for name in ("Caddyfile", "site.caddy", "tls-organization.caddy", "tls-internal-ca.caddy"):
        code = _code(name).lower()
        for token in forbidden:
            assert token not in code, f"{name} references {token!r} in the log path"

    site = _code("site.caddy")
    assert "log {" in site
    assert "output stdout" in site


def test_caddy_upstream_matches_the_compose_web_service() -> None:
    match = re.search(r"reverse_proxy ([a-z0-9_.-]+):(\d+)", _code("site.caddy"))
    assert match is not None
    upstream, port = match.group(1), match.group(2)
    assert upstream == "web"

    services = _compose()["services"]
    web = services[upstream]
    assert port in {str(item) for item in web["expose"]}
    assert set(web["networks"]) == {"edge", "proxy"}
    # The proxy is on that shared network only, never on edge/backend.
    assert set(services["caddy"]["networks"]) == {"proxy"}
