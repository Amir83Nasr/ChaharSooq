"""Commodity sources — live Parsina in production, local CSV in development.

`ProductSyncService` only depends on this small protocol, so validation, locking,
and apply rules stay identical regardless of where the rows came from.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from app.core.config import ParsinaSettings, Settings
from app.integrations.parsina import ParsinaClient
from app.integrations.parsina_csv import CsvCommoditySource

if TYPE_CHECKING:
    from httpx import BaseTransport

SourceLabel = Literal["parsina", "csv"]


class CommoditySource(Protocol):
    @property
    def label(self) -> SourceLabel: ...

    @property
    def is_configured(self) -> bool: ...

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
    """Development reads the CSV fixture; every other environment hits Parsina."""
    if app_settings.app_env == "development":
        return CsvCommoditySource(Path(app_settings.products_csv_path))
    return ParsinaCommoditySource(parsina_settings, transport=transport)
