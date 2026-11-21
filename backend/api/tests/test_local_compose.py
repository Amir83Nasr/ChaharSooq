"""Local Compose structure — hot-reload images and the PostgreSQL 19 data mount.

The file is parsed, not started: no Docker daemon is required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

COMPOSE_PATH = Path(__file__).resolve().parents[3] / "compose.local.yml"


def _compose() -> dict[str, Any]:
    with COMPOSE_PATH.open(encoding="utf-8") as handle:
        return cast(dict[str, Any], yaml.safe_load(handle))


def test_postgres_mounts_the_image_data_parent() -> None:
    """PostgreSQL 19 keeps its cluster below /var/lib/postgresql, not in /data."""
    volumes = _compose()["services"]["postgres"]["volumes"]

    assert "pgdata:/var/lib/postgresql" in volumes
    assert "pgdata:/var/lib/postgresql/data" not in volumes


def test_dev_services_do_not_reuse_production_style_images() -> None:
    """A stale :latest image may carry a standalone-server CMD without reload."""
    services = _compose()["services"]

    assert services["api"]["image"] == "chaharsooq-api:dev"
    assert services["web"]["image"] == "chaharsooq-web:dev"


def test_only_the_two_stateful_volumes_are_declared() -> None:
    """Anything else in the local volume list is either anonymous or orphaned."""
    assert set(_compose()["volumes"]) == {"pgdata", "backups"}


def test_web_mounts_source_directories_without_anonymous_volumes() -> None:
    """A target without a host source creates a hash-named Docker volume."""
    volumes = [str(volume) for volume in _compose()["services"]["web"]["volumes"]]

    assert all(":" in volume for volume in volumes)
    assert ".:/app" not in volumes
    assert "./apps/web/app:/app/apps/web/app" in volumes
    assert "./packages/ui/src:/app/packages/ui/src" in volumes
