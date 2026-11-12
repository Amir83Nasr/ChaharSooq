# pyright: reportPrivateUsage=false
"""PostgreSQL role provisioning — URL separation, grants, and secret safety.

These tests are offline. The only connection is a mock; the opt-in integration
test in ``test_role_grants_postgres.py`` exercises a disposable container.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest

import scripts.provision_database_roles as provision_script
from app.core.provisioning import (
    APPLICATION_SCHEMA,
    ProvisioningError,
    RoleProvisioningPlan,
    _application_grants,
    _role_statement,
    build_plan,
)

pytestmark = pytest.mark.usefixtures("isolated_settings")

APP_URL = "postgresql+psycopg://charsooq_app:app-secret@db.invalid:5432/charsooq"
MIGRATION_URL = "postgresql+psycopg://charsooq_migrator:migration-secret@db.invalid:5432/charsooq"


def _plan() -> RoleProvisioningPlan:
    return build_plan(APP_URL, MIGRATION_URL, "charsooq")


def test_plan_derives_both_roles_from_their_own_urls() -> None:
    plan = _plan()

    assert plan.app_role == "charsooq_app"
    assert plan.migrator_role == "charsooq_migrator"
    assert plan.database == "charsooq"
    assert plan.host == "db.invalid"
    assert plan.port == 5432


def test_plan_repr_never_contains_passwords() -> None:
    rendered = repr(_plan())

    assert "app-secret" not in rendered
    assert "migration-secret" not in rendered


def test_both_urls_must_use_different_roles() -> None:
    same_role = APP_URL.replace("charsooq_app", "charsooq_one")

    with pytest.raises(ProvisioningError, match="different PostgreSQL roles"):
        build_plan(same_role, same_role.replace("app-secret", "other"), "charsooq")


@pytest.mark.parametrize("reserved", ["charsooq", "postgres", "pg_monitor", "public"])
def test_administrative_and_reserved_roles_are_refused(reserved: str) -> None:
    app_url = APP_URL.replace("charsooq_app", reserved)

    with pytest.raises(ProvisioningError, match="dedicated non-administrative"):
        build_plan(app_url, MIGRATION_URL, "charsooq")


def test_urls_must_target_the_same_database() -> None:
    other_database = MIGRATION_URL.replace("/charsooq", "/other")

    with pytest.raises(ProvisioningError, match="same database host and name"):
        build_plan(APP_URL, other_database, "charsooq")


def test_urls_must_carry_role_passwords() -> None:
    with pytest.raises(ProvisioningError, match="role name and password"):
        build_plan(
            "postgresql+psycopg://charsooq_app@db.invalid/charsooq",
            MIGRATION_URL,
            "charsooq",
        )


def test_only_postgresql_urls_are_accepted() -> None:
    with pytest.raises(ProvisioningError, match="must be a PostgreSQL URL"):
        build_plan("sqlite+pysqlite:///:memory:", MIGRATION_URL, "charsooq")


@pytest.mark.parametrize("exists", [True, False])
def test_role_statements_never_grant_superuser(exists: bool) -> None:
    rendered = _role_statement("charsooq_app", "app-secret", exists=exists).as_string(None)

    assert ("ALTER ROLE" if exists else "CREATE ROLE") in rendered
    assert "LOGIN" in rendered
    assert "NOSUPERUSER" in rendered
    assert "NOCREATEDB" in rendered
    assert "NOCREATEROLE" in rendered
    assert "NOBYPASSRLS" in rendered
    assert "SUPERUSER" not in rendered.replace("NOSUPERUSER", "")


def test_application_grants_are_runtime_only() -> None:
    statements = [statement.as_string(None) for statement in _application_grants(_plan())]
    rendered = "\n".join(statements)

    assert f'GRANT USAGE ON SCHEMA "{APPLICATION_SCHEMA}"' in rendered
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES" in rendered
    assert "GRANT USAGE, SELECT ON ALL SEQUENCES" in rendered
    assert "REVOKE ALL ON SCHEMA" in rendered
    assert "GRANT ALL" not in rendered
    assert "TRUNCATE" not in rendered
    assert "REFERENCES" not in rendered
    assert "CREATE ON SCHEMA" not in rendered.replace(
        f'REVOKE CREATE ON SCHEMA "{APPLICATION_SCHEMA}" FROM PUBLIC', ""
    )
    assert "ALTER SCHEMA" in rendered
    assert "OWNER TO" in rendered
    assert 'TO "charsooq_app"' in rendered


def test_default_privileges_cover_future_tables_and_sequences() -> None:
    rendered = "\n".join(statement.as_string(None) for statement in _application_grants(_plan()))

    assert 'ALTER DEFAULT PRIVILEGES FOR ROLE "charsooq_migrator"' in rendered
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "charsooq_app"' in rendered
    assert 'GRANT USAGE, SELECT ON SEQUENCES TO "charsooq_app"' in rendered


def test_grant_statements_are_idempotent_by_construction() -> None:
    first = [statement.as_string(None) for statement in _application_grants(_plan())]
    second = [statement.as_string(None) for statement in _application_grants(_plan())]

    assert first == second
    # Every converging statement starts with an idempotent verb.
    for statement in first:
        assert statement.split(" ", 2)[0] in {"REVOKE", "GRANT", "ALTER"}


def test_admin_dsn_is_never_part_of_the_public_plan() -> None:
    plan = _plan()

    assert not hasattr(plan, "postgres_password")
    assert "admin-secret" not in repr(plan)


def test_cli_success_prints_no_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setattr(
        provision_script,
        "get_provisioning_settings",
        lambda: SimpleNamespace(
            database_url=APP_URL,
            migration_database_url=MIGRATION_URL,
            postgres_password="admin-secret",
        ),
    )

    def provision(_settings: object) -> RoleProvisioningPlan:
        return _plan()

    monkeypatch.setattr(provision_script, "provision_from_settings", provision)

    provision_script.main()

    captured = capsys.readouterr()
    assert "roles are ready" in captured.out
    assert captured.err == ""
    assert "app-secret" not in captured.out + captured.err
    assert "migration-secret" not in captured.out + captured.err
    assert APP_URL not in captured.out + captured.err


def test_cli_failure_exits_non_zero_without_leaking_urls(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")

    def failure(_settings: object) -> RoleProvisioningPlan:
        raise ProvisioningError(f"could not reach {APP_URL}")

    monkeypatch.setattr(
        provision_script,
        "get_provisioning_settings",
        lambda: SimpleNamespace(
            database_url=APP_URL,
            migration_database_url=MIGRATION_URL,
            postgres_password="admin-secret",
        ),
    )
    monkeypatch.setattr(provision_script, "provision_from_settings", failure)

    with pytest.raises(SystemExit) as exc:
        provision_script.main()

    error = capsys.readouterr().err
    assert exc.value.code == 1
    assert "provisioning failed" in error
    assert APP_URL not in error
    assert "app-secret" not in error


@pytest.fixture(autouse=True)
def _forbid_real_connections(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail loudly if a unit test tries to open a real PostgreSQL connection."""

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unit tests must not open a PostgreSQL connection")

    monkeypatch.setattr("app.core.provisioning.psycopg.connect", forbidden)
    yield
