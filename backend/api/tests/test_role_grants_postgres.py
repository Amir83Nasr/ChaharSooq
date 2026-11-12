# pyright: reportArgumentType=false, reportCallIssue=false, reportUnknownVariableType=false, reportUnknownMemberType=false
# ruff: noqa: S608 — table names in this disposable test are module constants.
"""Opt-in PostgreSQL grants test against a disposable container.

Set ``CHARSOOQ_TEST_POSTGRES_ADMIN_URL`` to a throwaway PostgreSQL instance
(for example ``docker run --rm -e POSTGRES_PASSWORD=test -e POSTGRES_DB=charsooq_test
-p 55432:5432 postgres:18``) and run pytest. The test creates the two
non-administrative roles and proves their real privileges, including a second
idempotent provisioning run. It is skipped by default so no test can reach a
real database.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Iterator
from urllib.parse import urlsplit

import psycopg
import pytest
from sqlalchemy.engine import make_url

from app.core.config import get_migration_settings
from app.core.migrations import apply_migrations
from app.core.provisioning import apply_provisioning, build_plan

ADMIN_URL_ENV = "CHARSOOQ_TEST_POSTGRES_ADMIN_URL"
ADMIN_URL = os.environ.get(ADMIN_URL_ENV, "")

pytestmark = [
    pytest.mark.skipif(
        not ADMIN_URL,
        reason=f"set {ADMIN_URL_ENV} to a disposable PostgreSQL admin URL",
    ),
    pytest.mark.usefixtures("isolated_settings"),
]

APP_ROLE = "charsooq_app_test"
MIGRATOR_ROLE = "charsooq_migrator_test"
PROBE_TABLE = "provisioning_probe"
DEFAULT_TABLE = "provisioning_probe_default"


def _dsn(role: str, password: str) -> str:
    parts = urlsplit(ADMIN_URL)
    host = parts.hostname or "127.0.0.1"
    port = parts.port or 5432
    database = parts.path.lstrip("/") or "charsooq_test"
    return f"postgresql://{role}:{password}@{host}:{port}/{database}"


def _admin_parts() -> tuple[str, str, str, int]:
    parsed = make_url(ADMIN_URL)
    if not parsed.username or not parsed.password or not parsed.database or not parsed.host:
        raise AssertionError("the test admin URL must include user, password, host, and database")
    return (
        parsed.username,
        parsed.password,
        parsed.database,
        parsed.port or 5432,
    )


@pytest.fixture()
def provisioned() -> Iterator[tuple[str, str]]:
    admin_user, admin_password, _database, _port = _admin_parts()
    app_password = secrets.token_urlsafe(24)
    migrator_password = secrets.token_urlsafe(24)
    app_url = _dsn(APP_ROLE, app_password)
    migration_url = _dsn(MIGRATOR_ROLE, migrator_password)
    plan = build_plan(app_url, migration_url, admin_user)

    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        for table in (PROBE_TABLE, DEFAULT_TABLE):
            admin.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')

    apply_provisioning(plan, postgres_user=admin_user, postgres_password=admin_password)
    try:
        yield app_url, migration_url
    finally:
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            for table in (PROBE_TABLE, DEFAULT_TABLE):
                admin.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')


def test_application_role_has_runtime_dml_but_no_ddl(provisioned: tuple[str, str]) -> None:
    app_url, migration_url = provisioned

    with psycopg.connect(migration_url) as migrator:
        migrator.execute(f"CREATE TABLE {PROBE_TABLE} (id serial PRIMARY KEY, name text NOT NULL)")
        migrator.commit()

    with psycopg.connect(app_url) as app:
        app.execute(f"INSERT INTO {PROBE_TABLE} (name) VALUES ('first')")
        app.execute(f"UPDATE {PROBE_TABLE} SET name = 'updated' WHERE name = 'first'")
        row = app.execute(f"SELECT name FROM {PROBE_TABLE}").fetchone()
        assert row == ("updated",)
        app.execute(f"DELETE FROM {PROBE_TABLE}")
        app.commit()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("CREATE TABLE should_not_exist (id integer)")
        app.rollback()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute(f"DROP TABLE {PROBE_TABLE}")
        app.rollback()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("CREATE ROLE should_not_exist LOGIN PASSWORD 'x'")
        app.rollback()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("SELECT * FROM alembic_version").fetchone()
        app.rollback()


def test_sequence_usage_is_granted(provisioned: tuple[str, str]) -> None:
    app_url, migration_url = provisioned

    with psycopg.connect(migration_url) as migrator:
        migrator.execute(f"CREATE TABLE {PROBE_TABLE} (id serial PRIMARY KEY, name text)")
        migrator.commit()

    with psycopg.connect(app_url) as app:
        sequence = app.execute(f"SELECT pg_get_serial_sequence('{PROBE_TABLE}', 'id')").fetchone()
        assert sequence is not None
        value = app.execute(f"SELECT nextval('{sequence[0]}')").fetchone()
        assert value is not None and value[0] == 1
        app.rollback()


def test_default_privileges_cover_tables_created_after_provisioning(
    provisioned: tuple[str, str],
) -> None:
    app_url, migration_url = provisioned

    with psycopg.connect(migration_url) as migrator:
        migrator.execute(f"CREATE TABLE {DEFAULT_TABLE} (id serial PRIMARY KEY, name text)")
        migrator.commit()

    with psycopg.connect(app_url) as app:
        app.execute(f"INSERT INTO {DEFAULT_TABLE} (name) VALUES ('after')")
        assert app.execute(f"SELECT name FROM {DEFAULT_TABLE}").fetchone() == ("after",)
        app.commit()


def test_migration_role_can_apply_the_real_migrations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove the migration role, not the administrator, can run Alembic.

    A throwaway database keeps this independent of the grant assertions above.
    """
    admin_user, admin_password, _database, _port = _admin_parts()
    database_name = f"charsooq_migration_test_{secrets.token_hex(4)}"
    app_password = secrets.token_urlsafe(24)
    migrator_password = secrets.token_urlsafe(24)

    parts = urlsplit(ADMIN_URL)
    host = parts.hostname or "127.0.0.1"
    port = parts.port or 5432
    app_url = f"postgresql://{APP_ROLE}:{app_password}@{host}:{port}/{database_name}"
    migration_url = (
        f"postgresql://{MIGRATOR_ROLE}:{migrator_password}@{host}:{port}/{database_name}"
    )

    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{database_name}"')

    try:
        plan = build_plan(app_url, migration_url, admin_user)
        apply_provisioning(plan, postgres_user=admin_user, postgres_password=admin_password)
        monkeypatch.setenv("MIGRATION_DATABASE_URL", migration_url)
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)
        get_migration_settings.cache_clear()

        apply_migrations()

        with psycopg.connect(migration_url) as migrator:
            tables = {
                row[0]
                for row in migrator.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                ).fetchall()
            }
        assert {"admins", "products", "alembic_version"} <= tables

        with psycopg.connect(app_url) as app:
            app.execute(
                "INSERT INTO products (name, sku, price, stock, created_at) "
                "VALUES ('migrated', 'MIGRATED-1', 1000, 1, now())"
            )
            assert (
                app.execute("SELECT price FROM products WHERE sku = 'MIGRATED-1'").fetchone()
                is not None
            )
            app.commit()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                app.execute("CREATE TABLE should_not_exist (id integer)")
            app.rollback()
    finally:
        get_migration_settings.cache_clear()
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')


def test_provisioning_is_idempotent_and_keeps_profile(
    provisioned: tuple[str, str],
) -> None:
    app_url, migration_url = provisioned
    admin_user, admin_password, _database, _port = _admin_parts()
    plan = build_plan(app_url, migration_url, admin_user)

    with psycopg.connect(migration_url) as migrator:
        migrator.execute(f"CREATE TABLE {PROBE_TABLE} (id serial PRIMARY KEY, name text)")
        migrator.commit()

    apply_provisioning(plan, postgres_user=admin_user, postgres_password=admin_password)

    with psycopg.connect(ADMIN_URL) as admin:
        for role in (APP_ROLE, MIGRATOR_ROLE):
            row = admin.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
                "FROM pg_roles WHERE rolname = %s",
                (role,),
            ).fetchone()
            assert row == (False, False, False, False)
        assert admin.execute(
            "SELECT has_schema_privilege(%s, 'public', 'CREATE')", (APP_ROLE,)
        ).fetchone() == (False,)
        assert admin.execute(
            "SELECT pg_has_role(%s, %s, 'MEMBER')", (APP_ROLE, MIGRATOR_ROLE)
        ).fetchone() == (False,)

    with psycopg.connect(app_url) as app:
        app.execute(f"INSERT INTO {PROBE_TABLE} (name) VALUES ('still-works')")
        assert app.execute(f"SELECT name FROM {PROBE_TABLE}").fetchone() == ("still-works",)
        app.commit()
