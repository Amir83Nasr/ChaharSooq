import json
import os
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Literal, cast

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from app.core.deployment import (
    is_production_deployment,
    resolve_runtime_deployment_env,
)

# Repository layout: backend/api/app/core/config.py → backend/api → repo root.
# Env files are resolved from this module, not the working directory, so the API,
# Alembic, and the seed scripts always read the same configuration.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[4]
# Shared root env (optional) is loaded first so per-app files can override it.
_ENV_FILES = (
    str(_REPO_ROOT / ".env.local"),
    str(_REPO_ROOT / ".env"),
    str(_BACKEND_DIR / ".env.local"),
    str(_BACKEND_DIR / ".env"),
)

# Only the development source reads this file; production uses Parsina.
_DEFAULT_PRODUCTS_CSV_PATH = _REPO_ROOT / "data" / "parsina.csv"

# Matches the development compose database. Production must never inherit it
# implicitly; see DatabaseSettings below.
DEFAULT_DATABASE_URL = "postgresql+psycopg://charsooq:charsooq@localhost:5433/charsooq"
SECRETS_DIR_ENV = "SECRETS_DIR"
_PRODUCTION_DATABASE_URL_ERROR = (
    "DATABASE_URL must be set explicitly in Production; the localhost development "
    "database is refused. Provide the DATABASE_URL environment variable or a "
    "'database_url' file in SECRETS_DIR."
)
_PRODUCTION_DATABASE_DIALECT_ERROR = (
    "DATABASE_URL must be a PostgreSQL URL in Production; the configured database "
    "is not PostgreSQL."
)
_PRODUCTION_DATABASE_HOST_ERROR = (
    "DATABASE_URL must not target localhost or a loopback address in Production; "
    "point it at the Production database host."
)
_PRODUCTION_DATABASE_INVALID_ERROR = (
    "DATABASE_URL is not a valid SQLAlchemy URL; provide a PostgreSQL URL for Production."
)
_PRODUCTION_MIGRATION_URL_ERROR = (
    "MIGRATION_DATABASE_URL must be set explicitly in Production; the application "
    "database URL is not accepted for migrations. Provide the MIGRATION_DATABASE_URL "
    "environment variable or a 'migration_database_url' file in SECRETS_DIR."
)
_PRODUCTION_MIGRATION_URL_NOT_DISTINCT_ERROR = (
    "MIGRATION_DATABASE_URL and DATABASE_URL must use different PostgreSQL roles in "
    "Production; the API and the migration runner may not share one role."
)
_PRODUCTION_PROVISIONING_URL_ERROR = (
    "DATABASE_URL and MIGRATION_DATABASE_URL must be set for database role "
    "provisioning; each needs its own PostgreSQL role."
)
_PRODUCTION_POSTGRES_ADMIN_ERROR = (
    "POSTGRES_PASSWORD must be provided for database role provisioning."
)
_PRODUCTION_MIGRATION_DIALECT_ERROR = (
    "MIGRATION_DATABASE_URL must be a PostgreSQL URL in Production; the configured "
    "database is not PostgreSQL."
)
_PRODUCTION_MIGRATION_HOST_ERROR = (
    "MIGRATION_DATABASE_URL must not target localhost or a loopback address in "
    "Production; point it at the Production database host."
)
_PRODUCTION_MIGRATION_INVALID_ERROR = (
    "MIGRATION_DATABASE_URL is not a valid SQLAlchemy URL; provide a PostgreSQL URL for Production."
)
_PROVISIONING_DATABASE_INVALID_ERROR = (
    "DATABASE_URL is not a valid SQLAlchemy PostgreSQL URL for role provisioning."
)
_PROVISIONING_MIGRATION_INVALID_ERROR = (
    "MIGRATION_DATABASE_URL is not a valid SQLAlchemy PostgreSQL URL for role provisioning."
)


def _configured_app_env() -> str:
    """APP_ENV without instantiating the full application Settings."""
    return os.environ.get("APP_ENV", "development").strip().lower()


def _is_loopback_host(host: str) -> bool:
    """True for localhost, loopback IPs, and IPv4-mapped loopback IPv6."""
    normalized = host.strip().strip("[]").rstrip(".").lower()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        address = ip_address(normalized)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    mapped = getattr(address, "ipv4_mapped", None)
    return bool(mapped is not None and mapped.is_loopback)


def _iter_url_hosts(parsed: URL) -> list[str]:
    """Collect the effective host values from a parsed SQLAlchemy URL.

    ``host`` is the main field; libpq-style query parameters (``host`` and
    ``hostaddr``) can override it, so they are inspected too. Values are
    handled as text, never by searching the raw URL string.
    """
    hosts: list[str] = []
    main_host = parsed.host
    if main_host and main_host.strip():
        hosts.append(main_host)
    for key in ("host", "hostaddr"):
        value = parsed.query.get(key)
        # Runtime query values may be a tuple for repeated keys even though the
        # URL typing used here narrows them to str.
        if isinstance(value, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            hosts.append(value)
        elif isinstance(value, (tuple, list)):
            hosts.extend(value)
    return hosts


#: Per-setting Production URL messages. Keeping them in one table means a new
#: URL setting cannot accidentally reuse another setting's error text (which is
#: the only place an operator sees which variable failed).
_PRODUCTION_URL_MESSAGES: dict[str, tuple[str, str, str]] = {
    "DATABASE_URL": (
        _PRODUCTION_DATABASE_INVALID_ERROR,
        _PRODUCTION_DATABASE_DIALECT_ERROR,
        _PRODUCTION_DATABASE_HOST_ERROR,
    ),
    "MIGRATION_DATABASE_URL": (
        _PRODUCTION_MIGRATION_INVALID_ERROR,
        _PRODUCTION_MIGRATION_DIALECT_ERROR,
        _PRODUCTION_MIGRATION_HOST_ERROR,
    ),
}


def _validate_production_database_url(url: str, *, setting_name: str = "DATABASE_URL") -> None:
    """Reject non-PostgreSQL, missing-host, and loopback Production URLs.

    Parsing uses SQLAlchemy's URL parser, not substring matching. Errors carry
    no URL, host, username, or password so a failed boot cannot leak secrets.
    """
    invalid_message, dialect_message, host_message = _PRODUCTION_URL_MESSAGES[setting_name]
    try:
        parsed = make_url(url)
    except (ArgumentError, ValueError):
        raise ValueError(invalid_message) from None

    if parsed.get_backend_name() != "postgresql":
        raise ValueError(dialect_message)

    hosts = _iter_url_hosts(parsed)
    if not hosts:
        # No host cannot be proven to be a remote, non-loopback Production host.
        raise ValueError(host_message)
    if any(_is_loopback_host(host) for host in hosts):
        raise ValueError(host_message)


def _configured_secrets_dir() -> Path | None:
    """Return the optional secret-file directory, without reading its contents."""
    raw = os.environ.get(SECRETS_DIR_ENV, "").strip()
    return Path(raw).expanduser() if raw else None


class SecretFileSettings(BaseSettings):
    """Settings base with optional one-value-per-file secret loading.

    ``SECRETS_DIR`` is read from the process environment. Secret files are named
    after their setting (``database_url``, ``session_secret``, ...) and are the
    lowest-priority source, so init arguments, environment variables, and env
    files keep their normal precedence.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        extra="ignore",
        # Pydantic's default ValidationError text includes the rejected input
        # (which can be a database URL or a secret). Never render it.
        hide_input_in_errors=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        secrets_dir = _configured_secrets_dir()
        if secrets_dir is None:
            return init_settings, env_settings, dotenv_settings, file_secret_settings
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            SecretsSettingsSource(settings_cls, secrets_dir=secrets_dir),
        )

    @model_validator(mode="after")
    def _validate_secrets_dir(self) -> "SecretFileSettings":
        secrets_dir = _configured_secrets_dir()
        if secrets_dir is not None and not secrets_dir.is_dir():
            raise ValueError(
                f"{SECRETS_DIR_ENV} must reference an existing directory (got {secrets_dir})"
            )
        return self


class DatabaseSettings(SecretFileSettings):
    """Application database configuration, usable without authentication settings.

    The API engine and the full application ``Settings`` use this model. It
    contains only the application role URL; Alembic and the migration runner use
    :class:`MigrationSettings` instead, so the API never reads the migration or
    administrative credential. Production refuses the localhost default so a
    missing database configuration cannot silently target the development
    database. The lock timeout remains a field here for compatibility with
    existing consumers; the migration models carry their own copy.
    """

    database_url: str = Field(default=DEFAULT_DATABASE_URL)
    #: How long a migration runner waits for another runner's advisory lock.
    migration_lock_timeout_seconds: float = Field(default=60.0, ge=0, le=3600)

    @field_validator("database_url", mode="before")
    @classmethod
    def _strip_database_url(cls, value: object) -> object:
        # Pasted Neon URLs can carry trailing whitespace ("sslmode=require "),
        # which psycopg rejects. Strip before SQLAlchemy sees it.
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _require_explicit_production_database_url(self) -> "DatabaseSettings":
        # Enforce the runtime identity here too: this model can be loaded
        # without the full Settings model, so APP_ENV=production must never
        # proceed with an unknown identity.
        resolve_runtime_deployment_env(_configured_app_env())

        url = self.database_url.strip()
        if not url:
            if is_production_deployment():
                raise ValueError(_PRODUCTION_DATABASE_URL_ERROR)
            self.database_url = DEFAULT_DATABASE_URL
        elif is_production_deployment() and url == DEFAULT_DATABASE_URL:
            raise ValueError(_PRODUCTION_DATABASE_URL_ERROR)
        else:
            self.database_url = url
            if is_production_deployment():
                _validate_production_database_url(url)
        return self


class MigrationSettings(SecretFileSettings):
    """Migration-only configuration for Alembic and the standalone runner.

    The API uses :class:`DatabaseSettings` and therefore never sees the
    migration credential. Alembic and ``scripts/migrate.py`` use this model
    instead, so a leaked application URL cannot run DDL.

    ``DATABASE_URL`` is accepted here only as a Development/Staging
    compatibility fallback while ``MIGRATION_DATABASE_URL`` is unset. In an
    explicitly identified Production deployment the migration URL is
    mandatory and the application URL is never used as a fallback.
    """

    #: Compatibility fallback; ignored in an explicit Production deployment.
    database_url: str = Field(default=DEFAULT_DATABASE_URL)
    #: Dedicated migration role URL. Set this in Production and preferably
    #: everywhere else too.
    migration_database_url: str = Field(default="")
    #: How long a migration runner waits for another runner's advisory lock.
    migration_lock_timeout_seconds: float = Field(default=60.0, ge=0, le=3600)

    @field_validator("database_url", "migration_database_url", mode="before")
    @classmethod
    def _strip_urls(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _resolve_migration_url(self) -> "MigrationSettings":
        # Alembic and the runner load without the full application Settings, so
        # the deployment identity is enforced here as well.
        resolve_runtime_deployment_env(_configured_app_env())

        app_url = self.database_url.strip()
        migration_url = self.migration_database_url.strip()

        if is_production_deployment():
            if not migration_url or migration_url == DEFAULT_DATABASE_URL:
                raise ValueError(_PRODUCTION_MIGRATION_URL_ERROR)
            _validate_production_database_url(migration_url, setting_name="MIGRATION_DATABASE_URL")
            if app_url and app_url != DEFAULT_DATABASE_URL:
                _validate_production_database_url(app_url, setting_name="DATABASE_URL")
                try:
                    shares_role = make_url(app_url).username == make_url(migration_url).username
                except (ArgumentError, ValueError):  # pragma: no cover — validated above
                    shares_role = True
                if shares_role:
                    raise ValueError(_PRODUCTION_MIGRATION_URL_NOT_DISTINCT_ERROR)
            self.migration_database_url = migration_url
            self.database_url = app_url or DEFAULT_DATABASE_URL
            return self

        # Development/Staging keep the previous single-URL behavior: when the
        # dedicated value is absent, migrations use DATABASE_URL. The fallback
        # is explicit and tested; it is never used in Production.
        self.migration_database_url = migration_url
        self.database_url = app_url or DEFAULT_DATABASE_URL
        return self

    @property
    def resolved_migration_database_url(self) -> str:
        """The URL Alembic must use (dedicated value, or the dev fallback)."""
        return self.migration_database_url or self.database_url


class ProvisioningSettings(SecretFileSettings):
    """Inputs for the one-shot PostgreSQL role provisioning service.

    This model is intentionally separate from :class:`DatabaseSettings` and
    :class:`Settings`: only the provisioning service receives the PostgreSQL
    administrator password. The API and the migration runner never instantiate
    it, so they can never read that secret.
    """

    #: Application role URL. Its role name and password are provisioned.
    database_url: str = Field(default="")
    #: Migration role URL. Its role name and password are provisioned.
    migration_database_url: str = Field(default="")
    #: Password of the container's administrative PostgreSQL role.
    postgres_password: str = Field(default="")
    #: Administrative role name created by the PostgreSQL image
    #: (``POSTGRES_USER``). It is used only to administer roles and grants.
    postgres_user: str = Field(default="charsooq")

    @field_validator(
        "database_url",
        "migration_database_url",
        "postgres_password",
        "postgres_user",
        mode="before",
    )
    @classmethod
    def _strip_values(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _require_provisioning_inputs(self) -> "ProvisioningSettings":
        resolve_runtime_deployment_env(_configured_app_env())

        if not self.database_url or not self.migration_database_url:
            raise ValueError(_PRODUCTION_PROVISIONING_URL_ERROR)
        if not self.postgres_password:
            raise ValueError(_PRODUCTION_POSTGRES_ADMIN_ERROR)
        if not self.postgres_user:
            raise ValueError("POSTGRES_USER must not be empty for role provisioning")

        for url, setting_name, invalid_message in (
            (self.database_url, "DATABASE_URL", _PROVISIONING_DATABASE_INVALID_ERROR),
            (
                self.migration_database_url,
                "MIGRATION_DATABASE_URL",
                _PROVISIONING_MIGRATION_INVALID_ERROR,
            ),
        ):
            try:
                parsed = make_url(url)
            except (ArgumentError, ValueError):
                raise ValueError(invalid_message) from None
            if parsed.get_backend_name() != "postgresql":
                raise ValueError(invalid_message)
            if is_production_deployment():
                _validate_production_database_url(url, setting_name=setting_name)
        return self


class Settings(DatabaseSettings):
    app_env: str = Field(default="development")
    # None means "not set by the operator"; the post-validation step below
    # applies the environment-specific default. Development and Staging run
    # both steps automatically, Production does not. An explicit true in
    # Production is rejected so the API never migrates or provisions itself.
    run_migrations_on_startup: bool | None = Field(default=None)
    # Separate switch: disabling migrations must not implicitly disable the
    # env-managed owner. Production uses the explicit owner CLI instead.
    run_owner_bootstrap_on_startup: bool | None = Field(default=None)
    session_secret: str = Field(default="dev-only-secret-change-me-min-32-chars")
    session_cookie_name: str = Field(default="charsooq_session")
    session_ttl_hours: int = Field(default=12)
    session_samesite: Literal["lax", "none"] = Field(default="lax")
    # Highest-privilege account, created/updated on every API boot. Legacy
    # ADMIN_USER / ADMIN_PASSWORD stay accepted as aliases for existing envs.
    owner_username: str = Field(
        default="superadmin",
        validation_alias=AliasChoices("OWNER_USERNAME", "ADMIN_USER", "owner_username"),
    )
    owner_password: str = Field(
        default="",
        validation_alias=AliasChoices("OWNER_PASSWORD", "ADMIN_PASSWORD", "owner_password"),
    )
    # Optional Redis URL for cross-worker rate limiting (e.g. redis://localhost:6379/0).
    # Empty means single-process in-memory limiting (dev / single replica).
    # Requires the optional `redis` library wherever set (see pyproject note).
    redis_url: str = Field(default="")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    # Development-only product catalog (app_env=development); ignored in production.
    products_csv_path: str = Field(default=str(_DEFAULT_PRODUCTS_CSV_PATH))
    # Production sync simulation: when set, APP_ENV=production syncs products
    # from this dev database instead of the live Parsina API, through the same
    # ProductSyncService path (button + scheduler behave identically).
    dev_database_url: str = Field(default="")
    competitor_request_interval_seconds: float = Field(default=5.0, ge=1, le=300)
    competitor_price_ttl_hours: int = Field(default=24, ge=1, le=720)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        # ponytail: رشته env تکی؛ لیست کامل هنگام CORS_ORIGINS صریح.
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return cast(list[str], parsed)
            return [o.strip() for o in raw.split(",") if o.strip()]
        return value

    @model_validator(mode="after")
    def _fail_fast_on_default_secret(self) -> "Settings":
        # APP_ENV=production requires an explicit identity (Staging also uses
        # production behavior). DatabaseSettings and MigrationSettings perform
        # the same check when loaded without this full model.
        resolve_runtime_deployment_env(self.app_env)

        # APP_ENV=production covers Staging and Production application behavior.
        # DEPLOYMENT_ENV=production additionally covers a process that was
        # explicitly identified as Production while APP_ENV is not yet flipped.
        if self.app_env == "production" or is_production_deployment():
            if self.session_secret == "dev-only-secret-change-me-min-32-chars":  # noqa: S105
                raise ValueError("SESSION_SECRET must be set explicitly in production")
            if len(self.session_secret.encode()) < 32:
                raise ValueError("SESSION_SECRET must be at least 32 bytes in production")
            if len(self.owner_password) < 8:
                raise ValueError("OWNER_PASSWORD must be at least 8 characters in production")
        self.owner_username = self.owner_username.strip()
        if not self.owner_username:
            raise ValueError("OWNER_USERNAME must not be empty")
        return self

    @model_validator(mode="after")
    def _apply_startup_step_policy(self) -> "Settings":
        """Default the startup steps per environment and refuse in Production.

        Development/Staging keep the automatic behavior; Production defaults
        both steps to false and rejects an explicit true. An API boot must not
        change the schema or provision the owner in Production: the ordered
        pre-start CLI steps are the only supported path.
        """
        production = is_production_deployment()
        if self.run_migrations_on_startup is None:
            self.run_migrations_on_startup = not production
        if self.run_owner_bootstrap_on_startup is None:
            self.run_owner_bootstrap_on_startup = not production

        if production:
            if self.run_migrations_on_startup:
                raise ValueError(
                    "RUN_MIGRATIONS_ON_STARTUP must be false in Production; run "
                    "scripts/migrate.py as the ordered pre-start step before the API"
                )
            if self.run_owner_bootstrap_on_startup:
                raise ValueError(
                    "RUN_OWNER_BOOTSTRAP_ON_STARTUP must be false in Production; run "
                    "scripts/bootstrap_owner.py explicitly after migrations"
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def source_mode(self) -> Literal["csv", "dev", "parsina", "off"]:
        """Product source mode — single place for the scheduler/sync branch."""
        if self.app_env == "development":
            return "csv"
        if self.is_production:
            return "dev" if self.dev_database_url.strip() else "parsina"
        return "off"


class ParsinaSettings(SecretFileSettings):
    """Parsina accounting API connection — secrets only via env or SECRETS_DIR."""

    parsina_base_url: str = Field(default="")
    parsina_username: str = Field(default="")
    parsina_password: str = Field(default="")
    parsina_org_id: int | None = Field(default=None)
    parsina_year: int | None = Field(default=None)
    parsina_ware_id: int | None = Field(default=None, description="optional LoadByFilter Ware")
    parsina_sale_type_id: int | None = Field(default=None, description="optional Saletype")
    parsina_timeout_seconds: float = Field(default=15.0, gt=0)
    parsina_sync_interval_minutes: int = Field(default=1440, ge=1)
    parsina_sync_enabled: bool = Field(default=True)

    @property
    def base_url(self) -> str:
        return self.parsina_base_url.strip().rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(
            self.base_url
            and self.parsina_username
            and self.parsina_password
            and self.parsina_org_id is not None
            and self.parsina_year is not None
        )


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Application database configuration used by the API engine."""
    return DatabaseSettings()


@lru_cache
def get_migration_settings() -> MigrationSettings:
    """Migration configuration for Alembic and the standalone runner."""
    return MigrationSettings()


@lru_cache
def get_provisioning_settings() -> ProvisioningSettings:
    """Role-provisioning configuration; only the one-shot service uses this."""
    return ProvisioningSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_parsina_settings() -> ParsinaSettings:
    return ParsinaSettings()
