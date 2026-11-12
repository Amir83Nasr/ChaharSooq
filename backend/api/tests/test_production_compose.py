"""Production Compose structure — service order and least-privilege secrets.

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


def test_production_services_are_complete_and_ordered_by_dependencies() -> None:
    services = _services()

    assert set(services) == {"db", "provision", "migrate", "api", "web"}

    assert _depends_on(services["provision"]) == {"db": "service_healthy"}
    assert _depends_on(services["migrate"]) == {
        "db": "service_healthy",
        "provision": "service_completed_successfully",
    }
    assert _depends_on(services["api"]) == {
        "db": "service_healthy",
        "migrate": "service_completed_successfully",
    }
    assert _depends_on(services["web"]) == {"api": "service_healthy"}


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


def test_one_shot_services_do_not_restart_and_the_database_is_not_published() -> None:
    services = _services()

    assert services["provision"]["restart"] == "no"
    assert services["migrate"]["restart"] == "no"
    assert "ports" not in services["db"]
    assert "ports" not in services["api"]
    assert "ports" not in services["web"]


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
