"""Commodity sources — live Parsina in production, local CSV in development.

`ProductSyncService` only depends on this small protocol, so validation, locking,
and apply rules stay identical regardless of where the rows came from.
When `DEV_DATABASE_URL` is set, production syncs from the dev database
instead of Parsina (button + scheduler simulation, see `dev_db.py`).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from app.core.config import ParsinaSettings, Settings
from app.integrations.dev_db import DevDatabaseCommoditySource
from app.integrations.parsina import ParsinaClient
from app.integrations.parsina_csv import CsvCommoditySource

if TYPE_CHECKING:
    from httpx import BaseTransport

SourceLabel = Literal["parsina", "csv", "dev"]


class CommoditySource(Protocol):
    @property
    def label(self) -> SourceLabel: ...

    @property
    def is_configured(self) -> bool: ...

    @property
    def is_full_catalog(self) -> bool:
        """True only when a successful fetch represents the complete sync scope.

        Missing-row deactivation is safe only for a complete listing of the same
        scope; scoped/filtered sources must not trigger global deactivation.
        """
        ...

    def fetch(self) -> tuple[list[Any], int | None, dict[int, str]]: ...


class ParsinaCommoditySource:
    def __init__(
        self, settings: ParsinaSettings, *, transport: BaseTransport | None = None
    ) -> None:
        self._settings = settings
        self._transport = transport

    @property
    def label(self) -> SourceLabel:
        return "parsina"

    @property
    def is_configured(self) -> bool:
        return self._settings.is_configured

    @property
    def is_full_catalog(self) -> bool:
        # LoadByFilter (Ware/Saletype) scopes results; deactivating products
        # outside that scope from a scoped response would be unsafe.
        return (
            self._settings.parsina_ware_id is None and self._settings.parsina_sale_type_id is None
        )

    def fetch(self) -> tuple[list[Any], int | None, dict[int, str]]:
        with ParsinaClient(self._settings, transport=self._transport) as client:
            rows, total = client.commodities()
            units = client.units()
        return rows, total, units


def build_commodity_source(
    *,
    app_settings: Settings,
    parsina_settings: ParsinaSettings,
    transport: BaseTransport | None = None,
) -> CommoditySource:
    """Development reads the CSV fixture; production reads Parsina or dev DB.

    `DEV_DATABASE_URL` switches production to the dev-database simulation:
    the sync button and the scheduler copy the dev mirror instead of calling
    Parsina, with identical validation, locking, and status reporting.
    """
    if app_settings.app_env == "development":
        return CsvCommoditySource(Path(app_settings.products_csv_path))
    if app_settings.dev_database_url.strip():
        return DevDatabaseCommoditySource(app_settings.dev_database_url)
    return ParsinaCommoditySource(parsina_settings, transport=transport)
