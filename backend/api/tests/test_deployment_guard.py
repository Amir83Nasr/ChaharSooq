"""Deployment identity guards — protected scripts fail closed, Development/Staging still work.

No test here opens a real database: allowed paths use a temporary SQLite file,
and rejection tests forbid any engine creation at all.
"""

from __future__ import annotations

import csv
import sys
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import scripts.clear_products as clear_products
import scripts.seed_admin as seed_admin
import scripts.seed_demo_competitors as seed_demo_competitors
import scripts.seed_parsina_products as seed_parsina_products
import scripts.sync_dev_to_prod as sync_dev_to_prod
from app.core.config import get_database_settings, get_settings
from app.core.database import Base, get_engine, reset_engine
from app.core.deployment import (
    DeploymentIdentityError,
    enforce_deployment_env,
    require_deployment_env,
    resolve_deployment_env,
)
from app.models import Admin, CompetitorListing, Product


@pytest.fixture(autouse=True)
def _clear_deployment_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every test starts without DEPLOYMENT_ENV, as a fresh shell would."""
    monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)
    yield


@pytest.fixture()
def sqlite_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[str]:
    """Point app settings at a temporary SQLite file (never a real database)."""
    url = f"sqlite:///{tmp_path / 'guard.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APP_ENV", "test")
    get_database_settings.cache_clear()
    get_settings.cache_clear()
    reset_engine()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    try:
        yield url
    finally:
        reset_engine()
        get_database_settings.cache_clear()
        get_settings.cache_clear()


@pytest.fixture()
def forbid_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any database access fail loudly so rejection tests prove fail-closed."""

    def fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a protected script touched the database before its identity guard")

    for module in (seed_admin, seed_demo_competitors, seed_parsina_products, clear_products):
        monkeypatch.setattr(module, "get_engine", fail)
    monkeypatch.setattr(sync_dev_to_prod, "sync", fail)


def _add_product(sku: str = "GUARD-1", name: str = "کالای آزمون") -> None:
    with Session(get_engine()) as session:
        session.add(
            Product(
                name=name,
                sku=sku,
                price=Decimal(100),
                stock=Decimal(1),
                main_group_name="لوازم خانگی",
            )
        )
        session.commit()


# ── GUARD UNIT BEHAVIOR ──────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("development", "development"),
        ("staging", "staging"),
        ("production", "production"),
        (" STAGING ", "staging"),
    ],
)
def test_resolve_known_identity(monkeypatch: pytest.MonkeyPatch, raw: str, expected: str) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", raw)
    assert resolve_deployment_env() == expected


def test_missing_identity_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)
    with pytest.raises(DeploymentIdentityError, match="DEPLOYMENT_ENV is not set"):
        resolve_deployment_env()


@pytest.mark.parametrize("raw", ["", "   ", "preprod", "prod", "local"])
def test_unknown_identity_fails_closed(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", raw)
    with pytest.raises(DeploymentIdentityError, match="DEPLOYMENT_ENV"):
        resolve_deployment_env()


def test_require_allows_only_listed_environments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")
    assert require_deployment_env("demo seed", ("development", "staging")) == "staging"
    with pytest.raises(DeploymentIdentityError, match="demo seed refuses"):
        require_deployment_env("demo seed", ("development",))


def test_app_env_does_not_replace_deployment_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Staging runs APP_ENV=production; only the explicit identity may decide."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_ENV", "development")
    assert resolve_deployment_env() == "development"


@pytest.mark.parametrize("app_env", ["development", "production"])
def test_app_env_alone_is_not_enough(monkeypatch: pytest.MonkeyPatch, app_env: str) -> None:
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)
    with pytest.raises(DeploymentIdentityError, match="DEPLOYMENT_ENV is not set"):
        resolve_deployment_env()


def test_enforce_exits_with_a_readable_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    with pytest.raises(SystemExit) as exc:
        enforce_deployment_env("seed_admin", ("development", "staging"))
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "seed_admin" in err
    assert "production" in err


# ── SCRIPT-LEVEL REJECTION ───────────────────────────────────

SCRIPT_CASES = [
    pytest.param(seed_admin.main, ["seed_admin.py"], id="seed-admin"),
    pytest.param(seed_parsina_products.main, ["seed_parsina_products.py"], id="seed-parsina"),
    pytest.param(clear_products.main, ["clear_products.py"], id="clear-products"),
    pytest.param(seed_demo_competitors.main, ["seed_demo_competitors.py"], id="seed-demo"),
    pytest.param(
        seed_demo_competitors.main,
        ["seed_demo_competitors.py", "--staging"],
        id="seed-demo-with-staging-flag",
    ),
    pytest.param(
        sync_dev_to_prod.main,
        ["sync_dev_to_prod.py", "--prod-url", "sqlite:///staging.db", "--yes"],
        id="sync-dev-to-prod",
    ),
]


@pytest.mark.parametrize(("run", "argv"), SCRIPT_CASES)
def test_scripts_refuse_explicit_production(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    forbid_database: None,
    run: Callable[[], object],
    argv: list[str],
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "production")
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        run()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "DEPLOYMENT_ENV=production" in err


@pytest.mark.parametrize(("run", "argv"), SCRIPT_CASES)
@pytest.mark.parametrize("identity", [None, "preprod"])
def test_scripts_refuse_missing_or_unknown_identity(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    forbid_database: None,
    run: Callable[[], object],
    argv: list[str],
    identity: str | None,
) -> None:
    if identity is None:
        monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)
    else:
        monkeypatch.setenv("DEPLOYMENT_ENV", identity)
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        run()
    assert exc.value.code == 1
    assert "DEPLOYMENT_ENV" in capsys.readouterr().err


def test_clear_products_refuses_staging(
    monkeypatch: pytest.MonkeyPatch, forbid_database: None
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")
    monkeypatch.setattr(sys, "argv", ["clear_products.py"])
    with pytest.raises(SystemExit) as exc:
        clear_products.main()
    assert exc.value.code == 1


def test_seed_parsina_refuses_staging(
    monkeypatch: pytest.MonkeyPatch, forbid_database: None
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")
    monkeypatch.setattr(sys, "argv", ["seed_parsina_products.py"])
    with pytest.raises(SystemExit) as exc:
        seed_parsina_products.main()
    assert exc.value.code == 1


def test_sync_refuses_development_destination(
    monkeypatch: pytest.MonkeyPatch, forbid_database: None
) -> None:
    """The dev → staging helper is cross-environment; it is not a local dev command."""
    monkeypatch.setenv("DEPLOYMENT_ENV", "development")
    monkeypatch.setattr(
        sys,
        "argv",
        ["sync_dev_to_prod.py", "--prod-url", "sqlite:///staging.db", "--yes"],
    )
    with pytest.raises(SystemExit) as exc:
        sync_dev_to_prod.main()
    assert exc.value.code == 1


# ── DEVELOPMENT / STAGING COMPATIBILITY ──────────────────────


@pytest.mark.parametrize("identity", ["development", "staging"])
def test_seed_admin_allowed_outside_production(
    monkeypatch: pytest.MonkeyPatch, sqlite_database: str, identity: str
) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENV", identity)
    monkeypatch.setenv("OWNER_USERNAME", "guard-owner")
    monkeypatch.setenv("OWNER_PASSWORD", "guard-pass-123")
    get_settings.cache_clear()

    seed_admin.main()

    with Session(get_engine()) as session:
        admin = session.scalar(select(Admin).where(Admin.username == "guard-owner"))
        assert admin is not None
        assert admin.role == "owner"


def test_clear_products_still_works_in_development(
    monkeypatch: pytest.MonkeyPatch, sqlite_database: str
) -> None:
    _add_product()
    with Session(get_engine()) as session:
        product_id = session.scalar(select(Product.id))
        assert product_id is not None
        session.add(
            CompetitorListing(
                product_id=product_id,
                store="digikala",
                url="https://www.digikala.com/product/dkp-1/",
            )
        )
        session.commit()

    monkeypatch.setenv("DEPLOYMENT_ENV", "development")
    assert clear_products.main() == 0

    with Session(get_engine()) as session:
        assert session.scalar(select(Product.id).limit(1)) is None
        assert session.scalar(select(CompetitorListing.id).limit(1)) is None


def test_seed_demo_allowed_in_development(
    monkeypatch: pytest.MonkeyPatch, sqlite_database: str
) -> None:
    _add_product()
    monkeypatch.setenv("DEPLOYMENT_ENV", "development")
    monkeypatch.setattr(sys, "argv", ["seed_demo_competitors.py"])

    assert seed_demo_competitors.main() == 0
    with Session(get_engine()) as session:
        assert session.scalar(select(CompetitorListing.id).limit(1)) is not None


def test_seed_demo_staging_requires_explicit_flag(
    monkeypatch: pytest.MonkeyPatch, sqlite_database: str
) -> None:
    _add_product()
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")

    monkeypatch.setattr(sys, "argv", ["seed_demo_competitors.py"])
    assert seed_demo_competitors.main() == 1

    monkeypatch.setattr(sys, "argv", ["seed_demo_competitors.py", "--staging"])
    assert seed_demo_competitors.main() == 0


def test_seed_parsina_still_works_in_development(
    monkeypatch: pytest.MonkeyPatch, sqlite_database: str, tmp_path: Path
) -> None:
    csv_path = tmp_path / "parsina.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["goodId", "goodCode", "goodName"])
        writer.writerow(["1", "CSV-1", "کالای CSV"])
    monkeypatch.setenv("DEPLOYMENT_ENV", "development")
    monkeypatch.setenv("PRODUCTS_CSV_PATH", str(csv_path))
    get_settings.cache_clear()
    monkeypatch.setattr(sys, "argv", ["seed_parsina_products.py"])

    assert seed_parsina_products.main() == 0
    with Session(get_engine()) as session:
        assert session.scalar(select(Product.sku).where(Product.sku == "CSV-1")) == "CSV-1"


def test_sync_allowed_for_staging_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_sync(dev_url: str, dest_url: str) -> dict[str, int]:
        calls.append((dev_url, dest_url))
        return {
            "categories": 0,
            "settings": 0,
            "products": 0,
            "competitor_listings_added": 0,
        }

    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")
    monkeypatch.setattr(sync_dev_to_prod, "sync", fake_sync)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_dev_to_prod.py",
            "--dev-url",
            "sqlite:///source.db",
            "--prod-url",
            "sqlite:///staging.db",
            "--yes",
        ],
    )

    assert sync_dev_to_prod.main() == 0
    assert calls == [("sqlite:///source.db", "sqlite:///staging.db")]


# ── MAKEFILE GUARDS (STATIC, NO DATABASE) ────────────────────

MAKEFILE = Path(__file__).resolve().parents[3] / "Makefile"
LEGACY_PROD_TARGETS = ["db-migrate-prod", "db-seed-prod", "db-sync-dev-to-prod"]
IDENTITY_TARGETS = [
    ("db-seed", "development"),
    ("db-seed-parsina", "development"),
    ("db-seed-demo", "development"),
    ("db-clear-products", "development"),
    ("db-sync-dev-to-staging", "staging"),
    ("db-seed-demo-staging", "staging"),
]


def _recipe(makefile: str, target: str) -> list[str]:
    lines = makefile.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("\t") or ":" not in line:
            continue
        if target not in line.split(":", 1)[0].split():
            continue
        recipe: list[str] = []
        for following in lines[index + 1 :]:
            if following.startswith("\t"):
                recipe.append(following.strip())
            elif following.strip():
                break
        return recipe
    raise AssertionError(f"Make target {target!r} not found")


@pytest.mark.parametrize("target", LEGACY_PROD_TARGETS)
def test_legacy_prod_make_targets_only_print_and_exit(target: str) -> None:
    recipe = _recipe(MAKEFILE.read_text(encoding="utf-8"), target)
    assert recipe, f"{target} has no recipe"
    assert all(line.startswith(("@echo", "@exit")) for line in recipe), recipe
    assert any(line.startswith("@exit 1") for line in recipe), recipe
    assert any("disabled" in line.lower() for line in recipe), recipe


def test_legacy_prod_aliases_point_to_the_disabled_target() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "sync-dev-to-prod sync-prod dev-to-prod: db-sync-dev-to-prod" in makefile


def test_makefile_does_not_read_the_legacy_prod_env_file() -> None:
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        if "--env-file" in line:
            assert ".env.production" not in line, line


@pytest.mark.parametrize(("target", "identity"), IDENTITY_TARGETS)
def test_make_targets_set_the_explicit_identity(target: str, identity: str) -> None:
    recipe = _recipe(MAKEFILE.read_text(encoding="utf-8"), target)
    assert any(f"DEPLOYMENT_ENV={identity}" in line for line in recipe), recipe
