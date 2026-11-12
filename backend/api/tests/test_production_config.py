"""Production configuration foundation — settings isolation and secret files.

Every test uses the ``isolated_settings`` fixture from conftest: real env files,
real secret directories, and unrelated environment variables are excluded.
No test opens a database connection.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

import app.core.migrations as migrations_module
import app.core.scheduler as scheduler_module
import app.main as main_module
import app.services.owner as owner_module
from app.core.config import (
    DEFAULT_DATABASE_URL,
    DatabaseSettings,
    MigrationSettings,
    ParsinaSettings,
    ProvisioningSettings,
    Settings,
    get_database_settings,
    get_migration_settings,
    get_parsina_settings,
    get_provisioning_settings,
    get_settings,
)
from app.core.deployment import is_production_deployment, resolve_deployment_env_optional

pytestmark = pytest.mark.usefixtures("isolated_settings")

PRODUCTION_DATABASE_URL = "postgresql+psycopg://app:test@db.invalid/charsooq"
SESSION_SECRET = "s" * 32
OWNER_PASSWORD = "owner-pass"


def _write_secret(directory: Path, name: str, value: str) -> None:
    (directory / name).write_text(f"{value}\n", encoding="utf-8")


def _use_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("OWNER_PASSWORD", OWNER_PASSWORD)


def _clear_caches() -> None:
    get_database_settings.cache_clear()
    get_migration_settings.cache_clear()
    get_provisioning_settings.cache_clear()
    get_settings.cache_clear()
    get_parsina_settings.cache_clear()


# ── DATABASE SETTINGS ────────────────────────────────────────


def test_database_settings_contain_only_database_and_migration_configuration() -> None:
    assert set(DatabaseSettings.model_fields) == {
        "database_url",
        "migration_lock_timeout_seconds",
    }


def test_api_settings_do_not_expose_the_migration_url() -> None:
    assert "migration_database_url" not in DatabaseSettings.model_fields
    assert "postgres_password" not in DatabaseSettings.model_fields


def test_migration_settings_are_separate_from_application_settings() -> None:
    assert "migration_database_url" in MigrationSettings.model_fields
    assert "migration_database_url" not in Settings.model_fields


def test_api_ignores_a_migration_url_and_uses_only_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_url = "postgresql+psycopg://migrator:secret@db.invalid/charsooq"
    monkeypatch.setenv("MIGRATION_DATABASE_URL", migration_url)

    settings = DatabaseSettings()

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert migration_url not in settings.model_dump().values()


def test_database_url_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql+psycopg://env:test@db.invalid/app"
    monkeypatch.setenv("DATABASE_URL", f"  {url}  ")

    assert DatabaseSettings().database_url == url


def test_database_url_from_secret_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    url = "postgresql+psycopg://file:test@db.invalid/app"
    _write_secret(tmp_path, "database_url", url)
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    _clear_caches()

    assert DatabaseSettings().database_url == url


def test_environment_wins_over_secret_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_secret(tmp_path, "database_url", "postgresql+psycopg://file:test@db.invalid/file")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env:test@db.invalid/env")
    _clear_caches()

    assert DatabaseSettings().database_url.endswith("/env")


def test_database_settings_do_not_require_authentication_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)

    settings = DatabaseSettings()

    assert settings.database_url == PRODUCTION_DATABASE_URL
    assert not hasattr(settings, "session_secret")
    assert not hasattr(settings, "owner_password")


def test_missing_database_url_keeps_development_default() -> None:
    assert DatabaseSettings().database_url == DEFAULT_DATABASE_URL


def test_empty_database_url_keeps_development_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "")

    assert DatabaseSettings().database_url == DEFAULT_DATABASE_URL


def test_empty_database_url_fails_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "")

    with pytest.raises(ValidationError, match="DATABASE_URL must be set explicitly"):
        DatabaseSettings()


def test_unknown_identity_is_not_treated_as_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "preprod")

    assert resolve_deployment_env_optional() is None
    assert DatabaseSettings().database_url == DEFAULT_DATABASE_URL


def test_production_refuses_localhost_database_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")

    with pytest.raises(ValidationError, match="DATABASE_URL must be set explicitly"):
        DatabaseSettings()


def test_production_rejects_the_exact_localhost_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    with pytest.raises(ValidationError, match="DATABASE_URL must be set explicitly"):
        DatabaseSettings()


def test_production_database_url_can_come_from_secret_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_secret(tmp_path, "database_url", PRODUCTION_DATABASE_URL)
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    _clear_caches()

    assert DatabaseSettings().database_url == PRODUCTION_DATABASE_URL


def test_explicit_missing_secrets_directory_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path / "missing"))

    with (
        pytest.warns(UserWarning, match="does not exist"),
        pytest.raises(ValidationError, match="SECRETS_DIR must reference an existing directory"),
    ):
        DatabaseSettings(database_url=PRODUCTION_DATABASE_URL)


# ── FULL APPLICATION SETTINGS ────────────────────────────────


def test_development_defaults_are_unchanged() -> None:
    settings = Settings()

    assert settings.app_env == "development"
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.run_migrations_on_startup is True
    assert settings.run_owner_bootstrap_on_startup is True
    assert settings.migration_lock_timeout_seconds == 60.0


def test_staging_keeps_production_app_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://staging:test@db.invalid/staging")
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("OWNER_PASSWORD", OWNER_PASSWORD)

    settings = Settings()

    assert settings.is_production is True
    assert settings.app_env == "production"
    assert settings.run_migrations_on_startup is True
    assert settings.run_owner_bootstrap_on_startup is True
    assert resolve_deployment_env_optional() == "staging"


def test_production_authentication_validation_remains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_production(monkeypatch)
    monkeypatch.setenv("SESSION_SECRET", "dev-only-secret-change-me-min-32-chars")
    with pytest.raises(ValidationError, match="SESSION_SECRET must be set explicitly"):
        Settings()

    monkeypatch.setenv("SESSION_SECRET", "too-short")
    with pytest.raises(ValidationError, match="SESSION_SECRET must be at least 32 bytes"):
        Settings()


def test_production_owner_password_validation_remains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_production(monkeypatch)
    monkeypatch.delenv("OWNER_PASSWORD")
    with pytest.raises(ValidationError, match="OWNER_PASSWORD must be at least 8"):
        Settings()

    monkeypatch.setenv("OWNER_PASSWORD", "short")
    with pytest.raises(ValidationError, match="OWNER_PASSWORD must be at least 8"):
        Settings()


def test_production_required_secrets_can_come_from_secret_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_secret(tmp_path, "database_url", PRODUCTION_DATABASE_URL)
    _write_secret(tmp_path, "session_secret", SESSION_SECRET)
    _write_secret(tmp_path, "owner_password", OWNER_PASSWORD)
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    _clear_caches()

    settings = Settings()

    assert settings.database_url == PRODUCTION_DATABASE_URL
    assert settings.session_secret == SESSION_SECRET
    assert settings.owner_password == OWNER_PASSWORD


def test_environment_overrides_secret_file_for_full_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_secret(tmp_path, "database_url", PRODUCTION_DATABASE_URL)
    _write_secret(tmp_path, "session_secret", "f" * 32)
    _write_secret(tmp_path, "owner_password", OWNER_PASSWORD)
    file_secret = "f" * 32
    environment_secret = "e" * 40
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("SESSION_SECRET", environment_secret)
    _clear_caches()

    settings = Settings()

    assert settings.session_secret == environment_secret
    assert settings.session_secret != file_secret
    assert settings.database_url == PRODUCTION_DATABASE_URL
    assert settings.owner_password == OWNER_PASSWORD


def test_production_empty_secrets_dir_fails_for_missing_session_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)
    _clear_caches()

    with pytest.raises(ValidationError, match="SESSION_SECRET must be set explicitly"):
        Settings()


def test_production_empty_secrets_dir_fails_for_missing_owner_password(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
    _clear_caches()

    with pytest.raises(ValidationError, match="OWNER_PASSWORD must be at least 8"):
        Settings()


def test_parsina_credentials_remain_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")

    # Parsina is independent of the application authentication secrets and is
    # disabled when its own required values are absent.
    parsina = ParsinaSettings()
    assert parsina.is_configured is False


def test_parsina_password_can_come_from_secret_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_secret(tmp_path, "parsina_password", "parsina-secret")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    _clear_caches()

    assert ParsinaSettings().parsina_password == "parsina-secret"


def test_legacy_environment_aliases_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ADMIN_USER", "legacy-owner")
    monkeypatch.setenv("ADMIN_PASSWORD", "legacy-password")
    monkeypatch.setenv("CORS_ORIGINS", "https://a.invalid, https://b.invalid")

    settings = Settings()

    assert settings.owner_username == "legacy-owner"
    assert settings.owner_password == "legacy-password"
    assert settings.cors_origins == ["https://a.invalid", "https://b.invalid"]


# ── STARTUP MIGRATION CONTROL ────────────────────────────────


def _run_lifespan() -> None:
    async def run() -> None:
        async with main_module.lifespan(FastAPI()):
            pass

    asyncio.run(run())


@pytest.mark.parametrize(
    ("startup_migrations", "startup_owner", "expected"),
    [
        (False, False, []),
        (False, True, ["owner"]),
        (True, False, ["migrations"]),
        (True, True, ["migrations", "owner"]),
    ],
)
def test_lifespan_honours_independent_startup_flags(
    monkeypatch: pytest.MonkeyPatch,
    startup_migrations: bool,
    startup_owner: bool,
    expected: list[str],
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="staging",
            run_migrations_on_startup=startup_migrations,
            run_owner_bootstrap_on_startup=startup_owner,
        ),
    )
    monkeypatch.setattr(migrations_module, "upgrade_to_head", lambda: calls.append("migrations"))
    monkeypatch.setattr(owner_module, "bootstrap_owner", lambda: calls.append("owner"))
    monkeypatch.setattr(scheduler_module, "build_scheduler", lambda: None)

    _run_lifespan()

    assert calls == expected


def test_lifespan_skips_migrations_and_owner_in_test_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="test",
            run_migrations_on_startup=True,
            run_owner_bootstrap_on_startup=True,
        ),
    )
    monkeypatch.setattr(migrations_module, "upgrade_to_head", lambda: calls.append("migrations"))
    monkeypatch.setattr(owner_module, "bootstrap_owner", lambda: calls.append("owner"))
    monkeypatch.setattr(scheduler_module, "build_scheduler", lambda: None)

    _run_lifespan()

    assert calls == []


def test_production_can_disable_startup_migrations_with_valid_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_production(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")

    settings = Settings()

    assert settings.run_migrations_on_startup is False


def test_production_can_disable_startup_owner_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_production(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RUN_OWNER_BOOTSTRAP_ON_STARTUP", "false")

    settings = Settings()

    assert settings.run_owner_bootstrap_on_startup is False
    assert settings.run_migrations_on_startup is False
    assert settings.owner_password == OWNER_PASSWORD


def test_production_can_disable_both_startup_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_production(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")
    monkeypatch.setenv("RUN_OWNER_BOOTSTRAP_ON_STARTUP", "false")

    settings = Settings()

    assert settings.run_migrations_on_startup is False
    assert settings.run_owner_bootstrap_on_startup is False


def test_production_disabled_migrations_do_not_weaken_auth_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_production(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")
    monkeypatch.setenv("SESSION_SECRET", "short")

    with pytest.raises(ValidationError, match="SESSION_SECRET must be at least 32 bytes"):
        Settings()


# ── EXPLICIT DEPLOYMENT IDENTITY AT RUNTIME ──────────────────


def test_app_env_production_requires_explicit_deployment_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("OWNER_PASSWORD", OWNER_PASSWORD)

    with pytest.raises(ValidationError, match="DEPLOYMENT_ENV must be set explicitly"):
        Settings()


def test_database_settings_require_identity_when_app_env_is_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)

    with pytest.raises(ValidationError, match="DEPLOYMENT_ENV must be set explicitly"):
        DatabaseSettings()


@pytest.mark.parametrize("identity", ["preprod", "prod", "local", " "])
def test_app_env_production_rejects_an_unknown_identity(
    monkeypatch: pytest.MonkeyPatch,
    identity: str,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", identity)
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("OWNER_PASSWORD", OWNER_PASSWORD)

    with pytest.raises(ValidationError, match="DEPLOYMENT_ENV"):
        Settings()


def test_app_env_production_with_staging_identity_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://staging:test@db.invalid/staging")
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("OWNER_PASSWORD", OWNER_PASSWORD)

    settings = Settings()

    assert settings.app_env == "production"
    assert resolve_deployment_env_optional() == "staging"
    assert is_production_deployment() is False


def test_explicit_production_identity_is_recognised(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_production(monkeypatch)

    settings = Settings()

    assert resolve_deployment_env_optional() == "production"
    assert is_production_deployment() is True
    assert settings.run_migrations_on_startup is False
    assert settings.run_owner_bootstrap_on_startup is False


def test_development_without_identity_keeps_previous_behavior() -> None:
    settings = Settings()

    assert resolve_deployment_env_optional() is None
    assert is_production_deployment() is False
    assert settings.run_migrations_on_startup is True
    assert settings.run_owner_bootstrap_on_startup is True


def test_staging_identity_keeps_database_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://staging:test@127.0.0.1:5432/staging")
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("OWNER_PASSWORD", OWNER_PASSWORD)

    settings = Settings()

    assert settings.database_url.endswith("/staging")


# ── PRODUCTION DATABASE URL VALIDATION ───────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://app:test@db.invalid/charsooq",
        "postgresql://app:test@db.example.com:5432/charsooq",
        "postgresql+psycopg://app:test@[2001:db8::10]:5432/charsooq",
    ],
)
def test_production_accepts_valid_postgresql_urls(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", url)

    assert DatabaseSettings().database_url == url


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("sqlite+pysqlite:///:memory:", "must be a PostgreSQL URL"),
        ("postgresql+psycopg://app:test@localhost:5432/charsooq", "loopback"),
        ("postgresql+psycopg://app:test@localhost.:5432/charsooq", "loopback"),
        ("postgresql+psycopg://app:test@127.0.0.1:5432/charsooq", "loopback"),
        ("postgresql+psycopg://app:test@127.20.30.40:5432/charsooq", "loopback"),
        ("postgresql+psycopg://app:test@[::1]:5432/charsooq", "loopback"),
        ("postgresql+psycopg://app:test@[::ffff:127.0.0.1]:5432/charsooq", "loopback"),
        ("postgresql+psycopg:///charsooq", "loopback"),
        ("postgresql+psycopg://app:test@db.invalid/charsooq?host=127.0.0.1", "loopback"),
        ("postgresql+psycopg://app:test@db.invalid/charsooq?hostaddr=::1", "loopback"),
    ],
)
def test_production_rejects_non_postgresql_and_loopback_urls(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    message: str,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", url)

    with pytest.raises(ValidationError) as exc:
        DatabaseSettings()

    rendered = str(exc.value)
    assert message in rendered
    assert url not in rendered
    assert "postgresql+psycopg" not in rendered


def test_production_rejects_a_malformed_database_url_without_echoing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+psycopg://app:very-secret@[::1/charsooq"
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", url)

    with pytest.raises(ValidationError) as exc:
        DatabaseSettings()

    rendered = str(exc.value)
    assert "not a valid SQLAlchemy URL" in rendered
    assert "very-secret" not in rendered
    assert "postgresql" not in rendered


def test_development_still_accepts_sqlite_and_the_local_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    assert DatabaseSettings().database_url == "sqlite+pysqlite:///:memory:"


# ── MIGRATION DATABASE URL ───────────────────────────────────

MIGRATION_DATABASE_URL = "postgresql+psycopg://migrator:test@db.invalid/charsooq"


def test_development_migration_url_falls_back_to_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+psycopg://app:test@localhost:5433/charsooq"
    monkeypatch.setenv("DATABASE_URL", url)

    settings = MigrationSettings()

    assert settings.migration_database_url == ""
    assert settings.resolved_migration_database_url == url


def test_development_migration_url_is_independent_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_url = "postgresql+psycopg://app:test@localhost:5433/charsooq"
    monkeypatch.setenv("DATABASE_URL", app_url)
    monkeypatch.setenv("MIGRATION_DATABASE_URL", MIGRATION_DATABASE_URL)

    settings = MigrationSettings()

    assert settings.migration_database_url == MIGRATION_DATABASE_URL
    assert settings.resolved_migration_database_url == MIGRATION_DATABASE_URL
    assert settings.resolved_migration_database_url != settings.database_url


def test_staging_migration_url_falls_back_to_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+psycopg://staging:test@db.invalid/staging"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", url)

    settings = MigrationSettings()

    assert settings.resolved_migration_database_url == url


def test_production_requires_migration_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)

    with pytest.raises(ValidationError, match="MIGRATION_DATABASE_URL must be set explicitly"):
        MigrationSettings()


def test_production_rejects_the_application_url_as_the_migration_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)
    monkeypatch.setenv("MIGRATION_DATABASE_URL", PRODUCTION_DATABASE_URL)

    with pytest.raises(ValidationError, match="must use different PostgreSQL roles"):
        MigrationSettings()


def test_production_accepts_independent_application_and_migration_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)
    monkeypatch.setenv("MIGRATION_DATABASE_URL", MIGRATION_DATABASE_URL)

    settings = MigrationSettings()

    assert settings.database_url == PRODUCTION_DATABASE_URL
    assert settings.migration_database_url == MIGRATION_DATABASE_URL
    assert settings.resolved_migration_database_url == MIGRATION_DATABASE_URL


def test_production_migration_url_can_come_from_secret_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_secret(tmp_path, "migration_database_url", MIGRATION_DATABASE_URL)
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    _clear_caches()

    assert MigrationSettings().resolved_migration_database_url == MIGRATION_DATABASE_URL


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("sqlite+pysqlite:///:memory:", "must be a PostgreSQL URL"),
        ("postgresql+psycopg://migrator:test@localhost:5432/charsooq", "loopback"),
        ("postgresql+psycopg://migrator:test@127.0.0.1:5432/charsooq", "loopback"),
        ("postgresql+psycopg://migrator:test@[::1]:5432/charsooq", "loopback"),
        ("postgresql+psycopg:///charsooq", "loopback"),
        (
            "postgresql+psycopg://migrator:test@db.invalid/charsooq?host=127.0.0.1",
            "loopback",
        ),
        ("postgresql+psycopg://migrator:very-secret@[::1/charsooq", "not a valid"),
    ],
)
def test_production_rejects_invalid_migration_urls_without_echoing_them(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    message: str,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("MIGRATION_DATABASE_URL", url)

    with pytest.raises(ValidationError) as exc:
        MigrationSettings()

    rendered = str(exc.value)
    assert message in rendered
    assert url not in rendered
    assert "very-secret" not in rendered
    assert "postgresql+psycopg" not in rendered


def test_provisioning_settings_require_both_urls_and_the_admin_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_DATABASE_URL)

    with pytest.raises(ValidationError, match="must be set for database role provisioning"):
        ProvisioningSettings()

    monkeypatch.setenv("MIGRATION_DATABASE_URL", MIGRATION_DATABASE_URL)
    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD must be provided"):
        ProvisioningSettings()


def test_provisioning_settings_accept_secret_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_secret(tmp_path, "database_url", PRODUCTION_DATABASE_URL)
    _write_secret(tmp_path, "migration_database_url", MIGRATION_DATABASE_URL)
    _write_secret(tmp_path, "postgres_password", "admin-secret")
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    _clear_caches()

    settings = ProvisioningSettings()

    assert settings.database_url == PRODUCTION_DATABASE_URL
    assert settings.migration_database_url == MIGRATION_DATABASE_URL
    assert settings.postgres_password == "admin-secret"
    assert settings.postgres_user == "charsooq"


# ── STARTUP FLAG DEFAULTS AND PRODUCTION POLICY ──────────────


def test_production_startup_flags_default_to_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_production(monkeypatch)

    settings = Settings()

    assert settings.run_migrations_on_startup is False
    assert settings.run_owner_bootstrap_on_startup is False


def test_development_explicit_startup_flags_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")
    monkeypatch.setenv("RUN_OWNER_BOOTSTRAP_ON_STARTUP", "false")

    settings = Settings()

    assert settings.run_migrations_on_startup is False
    assert settings.run_owner_bootstrap_on_startup is False


def test_staging_explicit_startup_flags_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://staging:test@db.invalid/staging")
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("OWNER_PASSWORD", OWNER_PASSWORD)
    monkeypatch.setenv("RUN_OWNER_BOOTSTRAP_ON_STARTUP", "false")

    settings = Settings()

    assert settings.run_migrations_on_startup is True
    assert settings.run_owner_bootstrap_on_startup is False


def test_production_rejects_startup_migrations_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_production(monkeypatch)
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "true")

    with pytest.raises(ValidationError, match="RUN_MIGRATIONS_ON_STARTUP must be false"):
        Settings()


def test_production_rejects_startup_owner_bootstrap_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_production(monkeypatch)
    monkeypatch.setenv("RUN_OWNER_BOOTSTRAP_ON_STARTUP", "true")

    with pytest.raises(ValidationError, match="RUN_OWNER_BOOTSTRAP_ON_STARTUP must be false"):
        Settings()
