"""Idempotent PostgreSQL role provisioning for the Production stack.

The Production database has three distinct roles:

* the image-created administrative role (``POSTGRES_USER``) — superuser, used
  only here and by the database container;
* the migration role — owns schema objects and has the DDL rights Alembic
  needs, but is not a superuser;
* the application role — only ``CONNECT``, schema ``USAGE``, and DML on
  application tables/sequences.

A dedicated one-shot Compose service runs this module on every stack start.
PostgreSQL initialization scripts only run when the data directory is first
created, so they cannot grant or rotate anything on an existing volume. Here
every statement is idempotent, and existing objects owned by the
administrative role are transferred to the migration role so a volume created
before the split keeps working.

Passwords come from secret files (through ``ProvisioningSettings`` and the two
database URLs). They are never printed, written to a file, or passed on a
command line. The module only renders them into the ``CREATE/ALTER ROLE``
statement PostgreSQL requires; SQLAlchemy/psycopg statement logging stays off.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg import sql
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from app.core.config import ProvisioningSettings

#: Separate from the Alembic advisory lock: provisioning and migrations must
#: not wait on each other's key by accident. ``int.from_bytes(b"csqroles")``.
PROVISIONING_LOCK_KEY = 0x637371726F6C6573

#: The schema the committed migrations actually create. There is no
#: ``schema=`` in ``backend/api/migrations``: every table lives in ``public``.
APPLICATION_SCHEMA = "public"

#: Conservative, lowercase identifier shape for the two provisioned roles.
#: Keeping this narrow avoids quoted-identifier surprises in URLs and SQL.
_ROLE_NAME_PATTERN = re.compile(r"[a-z_][a-z0-9_]{0,62}")

#: Never provision these as application/migration roles.
_RESERVED_ROLES = frozenset({"postgres", "pg_monitor", "pg_read_all_data", "public"})

#: Role attributes shared by both provisioned roles. No superuser, no createdb,
#: no createrole, no replication, no row-security bypass, and no inherited
#: memberships (role membership is also revoked explicitly).
_SAFE_ROLE_ATTRIBUTES = sql.SQL(
    "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
)

_APPLICATION_TABLE_PRIVILEGES = sql.SQL("SELECT, INSERT, UPDATE, DELETE")
_APPLICATION_SEQUENCE_PRIVILEGES = sql.SQL("USAGE, SELECT")

#: Tables the API never needs to touch. ``alembic_version`` is the migration
#: runner's bookkeeping; revoking it prevents a compromised application role
#: from rewriting the schema version.
_MIGRATION_BOOKKEEPING_TABLE = "alembic_version"

_OBJECT_KINDS: dict[str, sql.SQL] = {
    "r": sql.SQL("TABLE"),
    "p": sql.SQL("TABLE"),
    "v": sql.SQL("VIEW"),
    "m": sql.SQL("MATERIALIZED VIEW"),
    "f": sql.SQL("FOREIGN TABLE"),
    "S": sql.SQL("SEQUENCE"),
}


class ProvisioningError(RuntimeError):
    """Role provisioning cannot proceed safely; the transaction is rolled back."""


@dataclass(frozen=True)
class RoleProvisioningPlan:
    """Validated role names, target database, and credentials to provision."""

    app_role: str
    migrator_role: str
    database: str
    host: str
    port: int
    app_password: str = field(repr=False)
    migrator_password: str = field(repr=False)
    dsn_base: URL = field(repr=False)


def _parse_postgres_url(raw: str, setting_name: str) -> URL:
    try:
        parsed = make_url(raw)
    except (ArgumentError, ValueError):
        raise ProvisioningError(
            f"{setting_name} is not a valid PostgreSQL URL for role provisioning"
        ) from None
    if parsed.get_backend_name() != "postgresql":
        raise ProvisioningError(f"{setting_name} must be a PostgreSQL URL for role provisioning")
    return parsed


def build_plan(
    database_url: str,
    migration_database_url: str,
    postgres_user: str,
) -> RoleProvisioningPlan:
    """Validate the two URLs and derive the roles to create/grant.

    No connection is opened. Errors name the setting only, never a URL, host,
    username, or password.
    """
    app_url = _parse_postgres_url(database_url, "DATABASE_URL")
    migration_url = _parse_postgres_url(migration_database_url, "MIGRATION_DATABASE_URL")

    app_role = app_url.username
    app_password = app_url.password
    migrator_role = migration_url.username
    migrator_password = migration_url.password
    database = app_url.database
    host = app_url.host

    if not app_role or not app_password:
        raise ProvisioningError("DATABASE_URL must include the application role name and password")
    if not migrator_role or not migrator_password:
        raise ProvisioningError(
            "MIGRATION_DATABASE_URL must include the migration role name and password"
        )
    if not database or not host:
        raise ProvisioningError("the provisioning URLs must name an explicit database and host")

    # Both URLs must target the same database; otherwise provisioning would
    # harden one database while the services connect to another.
    if (
        database != migration_url.database
        or host != migration_url.host
        or (app_url.port or 5432) != (migration_url.port or 5432)
    ):
        raise ProvisioningError(
            "DATABASE_URL and MIGRATION_DATABASE_URL must target the same database host and name"
        )

    for role, setting_name in (
        (app_role, "DATABASE_URL"),
        (migrator_role, "MIGRATION_DATABASE_URL"),
    ):
        if role in _RESERVED_ROLES or role == postgres_user:
            raise ProvisioningError(
                f"{setting_name} must use a dedicated non-administrative PostgreSQL role"
            )
        if not _ROLE_NAME_PATTERN.fullmatch(role):
            raise ProvisioningError(
                f"{setting_name} role name must be lowercase letters, digits, or underscore"
            )

    if app_role == migrator_role:
        raise ProvisioningError(
            "DATABASE_URL and MIGRATION_DATABASE_URL must use different PostgreSQL roles"
        )

    return RoleProvisioningPlan(
        app_role=app_role,
        migrator_role=migrator_role,
        database=database,
        host=host,
        port=app_url.port or 5432,
        app_password=app_password,
        migrator_password=migrator_password,
        dsn_base=app_url,
    )


def _admin_dsn(plan: RoleProvisioningPlan, postgres_user: str, postgres_password: str) -> str:
    """Administrative DSN for this transaction; never logged or returned to a caller."""
    admin_url = plan.dsn_base.set(
        drivername="postgresql",
        username=postgres_user,
        password=postgres_password,
    )
    return admin_url.render_as_string(hide_password=False)


def _role_statement(role: str, password: str, *, exists: bool) -> sql.Composed:
    """Render an idempotent role upsert, including the password PostgreSQL needs."""
    action = sql.SQL("ALTER ROLE") if exists else sql.SQL("CREATE ROLE")
    return sql.SQL("{action} {role} WITH {attributes} PASSWORD {password}").format(
        action=action,
        role=sql.Identifier(role),
        attributes=_SAFE_ROLE_ATTRIBUTES,
        password=sql.Literal(password),
    )


def _role_exists(cursor: psycopg.Cursor[Any], role: str) -> bool:
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    return cursor.fetchone() is not None


def _application_grants(plan: RoleProvisioningPlan) -> list[sql.Composed]:
    """Exact privilege set for the application role.

    ``REVOKE`` first makes a re-run converge: a role that previously had a
    broader grant (for example ``TRUNCATE`` or ``CREATE``) loses it. The role
    is never made a schema owner and never receives DDL.
    """
    app = sql.Identifier(plan.app_role)
    migrator = sql.Identifier(plan.migrator_role)
    schema = sql.Identifier(APPLICATION_SCHEMA)
    database = sql.Identifier(plan.database)
    return [
        # Database: CONNECT only for the application; the migration role also
        # needs CREATE so future trusted extensions can be installed.
        sql.SQL("REVOKE ALL ON DATABASE {database} FROM {app}, {migrator}").format(
            database=database, app=app, migrator=migrator
        ),
        sql.SQL("GRANT CONNECT ON DATABASE {database} TO {app}").format(database=database, app=app),
        sql.SQL("GRANT CONNECT, CREATE ON DATABASE {database} TO {migrator}").format(
            database=database, migrator=migrator
        ),
        # Schema: the migration role owns it; the application only has USAGE.
        sql.SQL("ALTER SCHEMA {schema} OWNER TO {migrator}").format(
            schema=schema, migrator=migrator
        ),
        sql.SQL("REVOKE ALL ON SCHEMA {schema} FROM {app}").format(schema=schema, app=app),
        sql.SQL("REVOKE CREATE ON SCHEMA {schema} FROM PUBLIC").format(schema=schema),
        sql.SQL("GRANT USAGE ON SCHEMA {schema} TO {app}").format(schema=schema, app=app),
        # Existing objects: exact DML only.
        sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schema} FROM {app}").format(
            schema=schema, app=app
        ),
        sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {schema} FROM {app}").format(
            schema=schema, app=app
        ),
        sql.SQL("GRANT {privileges} ON ALL TABLES IN SCHEMA {schema} TO {app}").format(
            privileges=_APPLICATION_TABLE_PRIVILEGES,
            schema=schema,
            app=app,
        ),
        sql.SQL("GRANT {privileges} ON ALL SEQUENCES IN SCHEMA {schema} TO {app}").format(
            privileges=_APPLICATION_SEQUENCE_PRIVILEGES,
            schema=schema,
            app=app,
        ),
        # Future objects created by Alembic (the migration role) get the same
        # application privileges automatically. Revoke first so a broader
        # historical default cannot survive a re-run.
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {migrator} IN SCHEMA {schema} "
            "REVOKE ALL ON TABLES FROM {app}"
        ).format(migrator=migrator, schema=schema, app=app),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {migrator} IN SCHEMA {schema} "
            "REVOKE ALL ON SEQUENCES FROM {app}"
        ).format(migrator=migrator, schema=schema, app=app),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {migrator} IN SCHEMA {schema} "
            "GRANT {privileges} ON TABLES TO {app}"
        ).format(
            migrator=migrator,
            schema=schema,
            privileges=_APPLICATION_TABLE_PRIVILEGES,
            app=app,
        ),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {migrator} IN SCHEMA {schema} "
            "GRANT {privileges} ON SEQUENCES TO {app}"
        ).format(
            migrator=migrator,
            schema=schema,
            privileges=_APPLICATION_SEQUENCE_PRIVILEGES,
            app=app,
        ),
    ]


def _assert_superuser(cursor: psycopg.Cursor[Any]) -> None:
    cursor.execute("SELECT current_user, rolsuper FROM pg_roles WHERE rolname = current_user")
    row = cursor.fetchone()
    if row is None or row[1] is not True:
        raise ProvisioningError(
            "database role provisioning requires the PostgreSQL administrative role"
        )


def _harden_statement_logging(cursor: psycopg.Cursor[Any]) -> None:
    """Keep role passwords out of PostgreSQL's statement log for this transaction.

    The password still travels to the server inside ``ALTER ROLE ... PASSWORD``
    because PostgreSQL has no parameterized utility statement. These local
    settings suppress statement logging for this transaction on a server that
    logs statements; the module itself never logs the SQL.
    """
    cursor.execute("SET LOCAL log_statement = 'none'")
    cursor.execute("SET LOCAL log_min_duration_statement = -1")
    cursor.execute("SET LOCAL log_min_error_statement = 'panic'")


def _upsert_role(cursor: psycopg.Cursor[Any], role: str, password: str) -> None:
    cursor.execute(_role_statement(role, password, exists=_role_exists(cursor, role)))


def _revoke_all_memberships(cursor: psycopg.Cursor[Any], member: str) -> None:
    """Remove every role membership from a provisioned role, not only the known ones."""
    cursor.execute(
        """
        SELECT r.rolname
        FROM pg_auth_members AS m
        JOIN pg_roles AS r ON r.oid = m.roleid
        WHERE m.member = (SELECT oid FROM pg_roles WHERE rolname = %s)
          AND r.rolname <> %s
        """,
        (member, member),
    )
    for (role_name,) in cursor.fetchall():
        cursor.execute(
            sql.SQL("REVOKE {role} FROM {member}").format(
                role=sql.Identifier(role_name),
                member=sql.Identifier(member),
            )
        )


def _separate_memberships(
    cursor: psycopg.Cursor[Any], plan: RoleProvisioningPlan, admin_user: str
) -> None:
    app = sql.Identifier(plan.app_role)
    migrator = sql.Identifier(plan.migrator_role)
    admin = sql.Identifier(admin_user)
    for role, member in (
        (admin, app),
        (migrator, app),
        (app, migrator),
        (admin, migrator),
    ):
        cursor.execute(sql.SQL("REVOKE {role} FROM {member}").format(role=role, member=member))
    _revoke_all_memberships(cursor, plan.app_role)
    _revoke_all_memberships(cursor, plan.migrator_role)


def _transfer_existing_ownership(
    cursor: psycopg.Cursor[Any], plan: RoleProvisioningPlan, admin_user: str
) -> None:
    """Move objects from a pre-split volume's administrative owner to the migrator.

    Initialization scripts never run again on an existing volume, so a database
    created with the old single-role architecture still has tables owned by the
    administrative role. Alembic (as the migration role) could not ALTER them.
    Only objects owned by that known administrative role or by the migration
    role are accepted; anything else fails closed instead of being hijacked.
    """
    cursor.execute(
        """
        SELECT c.relname, c.relkind, pg_get_userbyid(c.relowner) AS owner
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = %s
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
          AND pg_get_userbyid(c.relowner) <> %s
        ORDER BY c.relname
        """,
        (APPLICATION_SCHEMA, plan.migrator_role),
    )
    rows = cursor.fetchall()
    for relname, relkind, owner in rows:
        if owner != admin_user:
            raise ProvisioningError(
                f"schema object {relname!r} is owned by an unexpected role; "
                "refusing to change its ownership"
            )
        object_kind = _OBJECT_KINDS.get(str(relkind))
        if object_kind is None:  # pragma: no cover — the query filters relkind
            raise ProvisioningError(f"unsupported schema object kind for {relname!r}")
        cursor.execute(
            sql.SQL("ALTER {kind} {object} OWNER TO {migrator}").format(
                kind=object_kind,
                object=sql.Identifier(relname),
                migrator=sql.Identifier(plan.migrator_role),
            )
        )


def _ensure_migration_bookkeeping(
    cursor: psycopg.Cursor[Any],
) -> None:
    """Create Alembic's version table before default privileges are applied.

    The migration role owns it (ownership is transferred below). Creating it
    here means the first provisioning run can revoke the application role's
    default privileges on it as well; otherwise a fresh volume would grant DML
    on ``alembic_version`` until the next provisioning run.
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS public.alembic_version (
            version_num VARCHAR(32) NOT NULL,
            CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
        )
        """
    )


def _protect_migration_bookkeeping(cursor: psycopg.Cursor[Any], plan: RoleProvisioningPlan) -> None:
    cursor.execute(
        "SELECT to_regclass(%s) IS NOT NULL",
        (f"{APPLICATION_SCHEMA}.{_MIGRATION_BOOKKEEPING_TABLE}",),
    )
    row = cursor.fetchone()
    if row is not None and row[0] is True:
        cursor.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {schema}.{table} FROM {app}, PUBLIC").format(
                schema=sql.Identifier(APPLICATION_SCHEMA),
                table=sql.Identifier(_MIGRATION_BOOKKEEPING_TABLE),
                app=sql.Identifier(plan.app_role),
            )
        )


def _verify(cursor: psycopg.Cursor[Any], plan: RoleProvisioningPlan, admin_user: str) -> None:
    """Fail closed if the post-state is not least privilege."""
    for role in (plan.app_role, plan.migrator_role):
        cursor.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
            "FROM pg_roles WHERE rolname = %s",
            (role,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ProvisioningError(f"role {role!r} was not created")
        if any(bool(flag) for flag in row):
            raise ProvisioningError(f"role {role!r} still has administrative attributes")

    cursor.execute(
        "SELECT has_schema_privilege(%s, %s, 'CREATE'), "
        "has_schema_privilege(%s, %s, 'USAGE'), "
        "has_database_privilege(%s, %s, 'CREATE')",
        (
            plan.app_role,
            APPLICATION_SCHEMA,
            plan.app_role,
            APPLICATION_SCHEMA,
            plan.app_role,
            plan.database,
        ),
    )
    row = cursor.fetchone()
    if row is None or row[0] is not False or row[1] is not True or row[2] is not False:
        raise ProvisioningError(
            "the application role does not have the expected schema/database privileges"
        )

    for granted_role in (plan.migrator_role, admin_user):
        cursor.execute("SELECT pg_has_role(%s, %s, 'MEMBER')", (plan.app_role, granted_role))
        row = cursor.fetchone()
        if row is None or row[0] is not False:
            raise ProvisioningError(
                "the application role must not be a member of an administrative or migration role"
            )

    for member in (plan.app_role, plan.migrator_role):
        cursor.execute(
            """
            SELECT count(*)
            FROM pg_auth_members AS m
            JOIN pg_roles AS r ON r.oid = m.roleid
            WHERE m.member = (SELECT oid FROM pg_roles WHERE rolname = %s)
              AND r.rolname <> %s
            """,
            (member, member),
        )
        row = cursor.fetchone()
        if row is None or row[0] != 0:
            raise ProvisioningError(f"role {member!r} still belongs to another role")

    cursor.execute(
        """
        SELECT count(*) FILTER (
                 WHERE pg_get_userbyid(c.relowner) = %s
               ),
               count(*) FILTER (
                 WHERE c.relkind IN ('r', 'p')
                   AND c.relname <> %s
                   AND NOT (
                     has_table_privilege(%s, c.oid, 'SELECT')
                     AND has_table_privilege(%s, c.oid, 'INSERT')
                     AND has_table_privilege(%s, c.oid, 'UPDATE')
                     AND has_table_privilege(%s, c.oid, 'DELETE')
                   )
               )
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = %s
          AND c.relkind IN ('r', 'p')
        """,
        (
            plan.app_role,
            _MIGRATION_BOOKKEEPING_TABLE,
            plan.app_role,
            plan.app_role,
            plan.app_role,
            plan.app_role,
            APPLICATION_SCHEMA,
        ),
    )
    row = cursor.fetchone()
    if row is None or row[0] != 0 or row[1] != 0:
        raise ProvisioningError(
            "the application role owns objects or lacks DML on an application table"
        )

    cursor.execute(
        "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = %s",
        (APPLICATION_SCHEMA,),
    )
    row = cursor.fetchone()
    if row is None or row[0] != plan.migrator_role:
        raise ProvisioningError(
            "the migration role must own the application schema after provisioning"
        )


def _apply(
    connection: psycopg.Connection[Any],
    plan: RoleProvisioningPlan,
    admin_user: str,
) -> None:
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (PROVISIONING_LOCK_KEY,))
            _assert_superuser(cursor)
            _harden_statement_logging(cursor)
            _upsert_role(cursor, plan.migrator_role, plan.migrator_password)
            _upsert_role(cursor, plan.app_role, plan.app_password)
            _separate_memberships(cursor, plan, admin_user)
            _ensure_migration_bookkeeping(cursor)
            for statement in _application_grants(plan):
                cursor.execute(statement)
            _transfer_existing_ownership(cursor, plan, admin_user)
            # The extension used by the search indexes is trusted, but creating
            # it here as the administrator keeps a fresh migration run simple.
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            _protect_migration_bookkeeping(cursor, plan)
            _verify(cursor, plan, admin_user)


def apply_provisioning(
    plan: RoleProvisioningPlan,
    *,
    postgres_user: str,
    postgres_password: str,
) -> None:
    """Provision roles/grants in one transaction against an existing database."""
    dsn = _admin_dsn(plan, postgres_user, postgres_password)
    with psycopg.connect(
        dsn,
        autocommit=False,
        application_name="charsooq-role-provisioning",
    ) as connection:
        _apply(connection, plan, postgres_user)


def provision_from_settings(settings: ProvisioningSettings) -> RoleProvisioningPlan:
    """Entry point for the one-shot Compose service."""
    plan = build_plan(
        settings.database_url,
        settings.migration_database_url,
        settings.postgres_user,
    )
    apply_provisioning(
        plan,
        postgres_user=settings.postgres_user,
        postgres_password=settings.postgres_password,
    )
    return plan


def redact_provisioning_error(message: str, settings: ProvisioningSettings | None) -> str:
    """Remove every provisioning secret from a message the CLI may print."""
    if settings is None:
        return message

    values: set[str] = {
        settings.database_url,
        settings.migration_database_url,
        settings.postgres_password,
    }
    for url in (settings.database_url, settings.migration_database_url):
        try:
            parsed = make_url(url)
        except (ArgumentError, ValueError):
            continue
        values.add(parsed.render_as_string(hide_password=False))
        if parsed.password:
            values.add(parsed.password)
    for value in sorted((value for value in values if value), key=len, reverse=True):
        message = message.replace(value, "<redacted>")
    return message
