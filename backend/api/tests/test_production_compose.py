"""Production Compose structure — a single api/web pair and least-privilege secrets.

The file is parsed, not started: no Docker daemon or secret file is required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

pytestmark = pytest.mark.usefixtures("isolated_settings")

COMPOSE_PATH = Path(__file__).resolve().parents[3] / "compose.production.yml"


def _compose() -> dict[str, Any]:
    with COMPOSE_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return cast(dict[str, Any], data)


def _services() -> dict[str, Any]:
    return _compose()["services"]


def _secrets(service: dict[str, Any]) -> set[str]:
    return {str(item) for item in service.get("secrets", [])}


def _depends_on(service: dict[str, Any]) -> dict[str, str]:
    return {
        name: str(condition.get("condition"))
        for name, condition in service.get("depends_on", {}).items()
    }


def _networks(service: dict[str, Any]) -> set[str]:
    networks = service.get("networks", [])
    if isinstance(networks, dict):
        return {str(name) for name in networks}
    return {str(name) for name in networks}


def test_production_services_define_the_base_and_one_deployable_pair() -> None:
    services = _services()

    assert set(services) == {"db", "provision", "migrate", "caddy", "api", "web"}

    assert _depends_on(services["provision"]) == {"db": "service_healthy"}
    assert _depends_on(services["migrate"]) == {
        "db": "service_healthy",
        "provision": "service_completed_successfully",
    }
    assert _depends_on(services["web"]) == {"api": "service_healthy"}
    # Caddy proxies the single `web` service; no compose-level slot coupling.
    assert "depends_on" not in services["caddy"]
    for name in ("api", "web"):
        assert "profiles" not in services[name]


def test_api_receives_only_the_application_credential() -> None:
    api = _services()["api"]

    assert _secrets(api) == {
        "database_url",
        "session_secret",
        "owner_password",
        "parsina_password",
    }
    assert "postgres_password" not in _secrets(api)
    assert "migration_database_url" not in _secrets(api)
    assert "DATABASE_URL" not in api.get("environment", {})
    assert "MIGRATION_DATABASE_URL" not in api.get("environment", {})


def test_migration_runner_receives_only_the_migration_credential() -> None:
    migrate = _services()["migrate"]

    assert _secrets(migrate) == {"migration_database_url"}
    assert "postgres_password" not in _secrets(migrate)
    assert "database_url" not in _secrets(migrate)


def test_provisioning_receives_only_what_it_needs() -> None:
    provision = _services()["provision"]

    assert _secrets(provision) == {
        "postgres_password",
        "database_url",
        "migration_database_url",
    }
    assert "session_secret" not in _secrets(provision)
    assert "owner_password" not in _secrets(provision)
    assert provision.get("environment", {}).get("POSTGRES_USER") == "charsooq"
    # postgres_password is owned by the PostgreSQL image user and mode 0440.
    assert "999" in provision.get("group_add", [])


def test_database_container_receives_only_the_admin_password() -> None:
    db = _services()["db"]

    assert _secrets(db) == {"postgres_password"}
    assert db["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/postgres_password"
    assert "database_url" not in _secrets(db)


def test_every_service_has_bounded_container_logs() -> None:
    """An unbounded json-file stream can fill the host disk and stop PostgreSQL."""

    for name, service in _services().items():
        logging = service.get("logging")
        assert logging == {
            "driver": "json-file",
            "options": {"max-size": "10m", "max-file": "5"},
        }, f"{name} must rotate its container logs"


def test_one_shot_services_do_not_restart_and_only_the_proxy_publishes_ports() -> None:
    services = _services()

    assert services["provision"]["restart"] == "no"
    assert services["migrate"]["restart"] == "no"
    for name in ("db", "api", "web"):
        assert "ports" not in services[name], name
    assert {name for name, service in services.items() if service.get("ports")} == {"caddy"}


def test_proxy_binds_http_and_https_to_one_explicit_internal_ip() -> None:
    ports = [str(port) for port in _services()["caddy"]["ports"]]

    # host_ip:host_port:container_port — a bare "80:80" would publish on every
    # interface, including anything routable from outside the internal network.
    assert ports == [
        "${CHARSOOQ_PROXY_BIND_IP:?set CHARSOOQ_PROXY_BIND_IP to the approved internal IP}:80:80",
        "${CHARSOOQ_PROXY_BIND_IP:?set CHARSOOQ_PROXY_BIND_IP to the approved internal IP}:443:443",
    ]
    assert not any("0.0.0.0" in port or "[::]" in port for port in ports)  # noqa: S104


def test_network_topology_keeps_the_proxy_away_from_api_and_database() -> None:
    services = _services()

    assert _networks(services["db"]) == {"backend"}
    assert _networks(services["provision"]) == {"backend"}
    assert _networks(services["migrate"]) == {"backend"}
    assert _networks(services["api"]) == {"backend", "edge"}
    assert _networks(services["web"]) == {"edge", "proxy"}
    # Caddy reaches web only; it has no route to the API, PostgreSQL, or the
    # one-shot provisioning/migration services.
    assert _networks(services["caddy"]) == {"proxy"}


def test_networks_are_declared_without_guessed_subnets() -> None:
    networks = _compose()["networks"]

    assert set(networks) == {"backend", "edge", "proxy"}
    assert networks["backend"]["internal"] is True
    assert "ipam" not in networks["proxy"]
    edge = networks["edge"]["ipam"]["config"][0]["subnet"]
    assert str(edge).startswith("${CHARSOOQ_EDGE_SUBNET")


def test_api_trusts_only_its_web_container() -> None:
    services = _services()
    api = services["api"]
    web = services["web"]

    assert api["environment"]["FORWARDED_ALLOW_IPS"] == web["networks"]["edge"]["ipv4_address"]
    assert str(api["environment"]["FORWARDED_ALLOW_IPS"]).startswith("${CHARSOOQ_WEB_EDGE_IP")
    # FORWARDED_ALLOW_IPS=* would let any caller spoof the login rate-limit key.
    assert "*" not in str(api["environment"]["FORWARDED_ALLOW_IPS"])
    # The web image bakes http://api:8000, so the API must be named `api`.
    assert "api" in api["networks"]["edge"].get("aliases", [])


def test_caddy_is_pinned_isolated_and_keeps_certificate_state() -> None:
    caddy = _services()["caddy"]
    volumes = [str(volume) for volume in caddy["volumes"]]

    assert caddy["image"] == "caddy:2.11.9-alpine"
    assert "latest" not in caddy["image"]
    assert caddy["read_only"] is True
    assert "ALL" in caddy["cap_drop"]
    assert "NET_BIND_SERVICE" in caddy["cap_add"]
    assert "no-new-privileges:true" in caddy["security_opt"]
    assert "network_mode" not in caddy

    assert "./deploy/caddy:/etc/caddy:ro" in volumes
    assert any(volume.startswith("caddy_data:/data") for volume in volumes)
    assert any(volume.startswith("caddy_config:/config") for volume in volumes)
    assert {"caddy_data", "caddy_config"} <= set(_compose()["volumes"])
    assert not any("docker.sock" in volume for volume in volumes)
    assert all(volume.endswith(":ro") for volume in volumes if not volume.startswith("caddy_"))
    env = caddy.get("environment", {})
    assert env.get("CHARSOOQ_PUBLIC_SCHEME") == "${CHARSOOQ_PUBLIC_SCHEME:-https}"
    assert env.get("CHARSOOQ_PUBLIC_PORT") == "${CHARSOOQ_PUBLIC_PORT:-443}"
    assert env.get("CHARSOOQ_TLS_MODE") == "${CHARSOOQ_TLS_MODE:-organization}"
    assert env.get("CHARSOOQ_CADDY_AUTO_HTTPS") == "${CHARSOOQ_CADDY_AUTO_HTTPS:-off}"


def test_every_mounted_secret_is_declared_at_the_top_level() -> None:
    compose = _compose()
    declared = set(compose["secrets"])

    assert {"postgres_password", "database_url", "migration_database_url"} <= declared
    assert compose["secrets"]["migration_database_url"]["file"].endswith("/migration_database_url")


def test_provision_and_migration_commands_are_scripts_not_inline_sql() -> None:
    services = _services()

    assert services["provision"]["command"] == [
        "python",
        "backend/api/scripts/provision_database_roles.py",
    ]
    assert services["migrate"]["command"] == ["python", "backend/api/scripts/migrate.py"]


def test_production_images_are_explicit_and_have_no_moving_default() -> None:
    """An unset or moving image reference must fail the stack, not deploy a stale build."""

    services = _services()

    api_image = str(services["api"]["image"])
    web_image = str(services["web"]["image"])
    assert api_image.startswith("${CHAHARSOQ_API_IMAGE:?")
    assert web_image.startswith("${CHARSOOQ_WEB_IMAGE:?")
    assert ":-" not in api_image
    assert ":-" not in web_image
    assert services["provision"]["image"] == api_image
    assert services["migrate"]["image"] == api_image
    for name, service in services.items():
        assert "latest" not in str(service.get("image", "")), name


def test_production_images_are_pulled_rather_than_rebuilt() -> None:
    for name in ("provision", "migrate", "api", "web"):
        assert _services()[name].get("pull_policy") == "missing", name


def test_local_builds_carry_the_oci_release_metadata() -> None:
    """Even the host-build fallback must say which commit it came from."""

    services = _services()

    api_args = services["api"]["build"]["args"]
    web_args = services["web"]["build"]["args"]
    for args in (api_args, web_args):
        assert args["VCS_REF"] == "${CHARSOOQ_BUILD_REVISION:-unknown}"
        assert args["BUILD_DATE"] == "${CHARSOOQ_BUILD_DATE:-unknown}"
        assert args["VERSION"] == "${CHARSOOQ_BUILD_VERSION:-unknown}"
        assert args["SOURCE"] == "${CHARSOOQ_BUILD_SOURCE:-unknown}"
    assert web_args["API_URL_INTERNAL"] == "http://api:8000"
