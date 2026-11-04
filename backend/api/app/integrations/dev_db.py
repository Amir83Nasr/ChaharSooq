"""Dev-database commodity source — production sync simulation without Parsina.

When `DEV_DATABASE_URL` is set, production builds this source instead of the
live Parsina client: the "به‌روزرسانی از پارسینا" button (and the scheduler)
copies the dev product mirror into the prod database through the exact same
`ProductSyncService` validation/apply path. No network, no credentials.

Only active dev rows are listed, so a product deactivated or removed in dev
deactivates the prod mirror on the next run — the same rule a complete
Parsina listing enforces. Connection strings never appear in errors/logs.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.catalog import Product

log = logging.getLogger("charsooq")

_DEV_UNIT_FALLBACK = "عدد"


class DevDbSourceError(Exception):
    """The dev database is unreachable or returned an unusable catalog."""


class DevDatabaseCommoditySource:
    """Read the dev product mirror on demand; the prod sync treats it as complete."""

    def __init__(self, url: str) -> None:
        self._url = url.strip()

    @property
    def label(self) -> Literal["dev"]:
        return "dev"

    @property
    def is_configured(self) -> bool:
        return bool(self._url)

    def fetch(self) -> tuple[list[dict[str, Any]], int | None, dict[int, str]]:
        """Raw Parsina-shaped rows + reported total + unit titles."""
        if not self._url:
            raise DevDbSourceError("آدرس دیتابیس dev تنظیم نشده است")
        try:
            if self._url.startswith("sqlite"):
                engine = create_engine(
                    self._url,
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False},
                )
            else:
                engine = create_engine(self._url, pool_pre_ping=True)
            with Session(engine) as session:
                products = list(
                    session.execute(select(Product).where(Product.is_active.is_(True))).scalars()
                )
        except SQLAlchemyError as exc:
            raise DevDbSourceError("اتصال به دیتابیس dev برقرار نشد") from exc
        except (OSError, ValueError) as exc:
            raise DevDbSourceError("اتصال به دیتابیس dev برقرار نشد") from exc
        finally:
            try:
                engine.dispose()  # type: ignore[possibly-undefined]
            except Exception:  # noqa: BLE001 — dispose must not mask fetch errors
                log.warning("dev-db engine dispose failed", exc_info=True)

        rows: list[dict[str, Any]] = [_to_raw(p) for p in products]
        return rows, len(rows), _unit_titles(products)


def _to_raw(product: Product) -> dict[str, Any]:
    """Map one dev mirror row back to the Parsina `/Commodity` field shape."""
    good_id = product.external_id if product.external_id is not None else product.id
    return {
        "goodId": good_id,
        "goodCode": product.sku,
        "goodName": product.name,
        "mainGroup": product.main_group_id,
        "subGroup": product.sub_group_id,
        "mainGroupName": product.main_group_name,
        "subGroupName": product.sub_group_name,
        "countUnit": product.unit_id,
        "weight": product.weight,
        "khas": product.is_special,
        "salePackPrice": product.sale_pack_price,
        "saleBoxPrice": product.sale_box_price,
        "usePrice": product.use_price,
        "discount": product.discount,
        "extra": product.extra,
        "numberInBox": product.number_in_box,
        "numberInPack": product.number_in_pack,
        "buyPrice": product.buy_price,
        "salePrice": product.price,
        "remain": product.stock,
        "wareRemain": product.ware_remain,
    }


def _unit_titles(products: list[Product]) -> dict[int, str]:
    """Mirror the Parsina units call from the unit names stored in dev."""
    titles: dict[int, str] = {}
    for product in products:
        if product.unit_id is not None:
            titles[product.unit_id] = product.unit_name or _DEV_UNIT_FALLBACK
    return titles
