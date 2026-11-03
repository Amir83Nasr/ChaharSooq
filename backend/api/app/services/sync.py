"""Product sync service — one path for manual button and the scheduler.

Rules:
  * identity = Parsina goodId; re-runs update instead of duplicating;
  * nothing is written until the whole payload validates;
  * a short/invalid listing is rejected (previous data untouched);
  * rows missing from a complete listing are deactivated, never deleted;
  * failures never overwrite `last_success_at`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.config import ParsinaSettings, get_parsina_settings, get_settings
from app.integrations.dev_db import DevDbSourceError
from app.integrations.parsina import (
    CommodityRow,
    ParsinaAuthError,
    ParsinaError,
    ParsinaNetworkError,
    ParsinaResponseError,
    parse_commodity,
)
from app.integrations.parsina_csv import CsvSourceError
from app.integrations.sources import (
    CommoditySource,
    ParsinaCommoditySource,
    SourceLabel,
    build_commodity_source,
)
from app.models import ParsinaSyncState, Product
from app.repositories import ProductRepository, SyncStateRepository

if TYPE_CHECKING:
    from httpx import BaseTransport

log = logging.getLogger("charsooq.sync")

LOCK_SECONDS = 30 * 60
SYNC_INTERVAL_MINUTES = 15


class SyncBusyError(Exception):
    """Another sync run holds the lock."""


class SyncNotConfiguredError(Exception):
    """Missing Parsina credentials/org/year."""


@dataclass(frozen=True)
class SyncResult:
    processed: int
    created: int
    updated: int
    deactivated: int
    skipped: int


def _money(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal("0")


def _stock(row: CommodityRow) -> Decimal:
    return row.remain if row.remain is not None else (row.ware_remain or Decimal("0"))


class ProductSyncService:
    def __init__(
        self,
        session: Session,
        *,
        settings: ParsinaSettings | None = None,
        transport: BaseTransport | None = None,
        source: CommoditySource | None = None,
    ) -> None:
        self._session = session
        self._source = source or self._default_source(settings, transport)
        self._sync_state = SyncStateRepository(session)
        self._products = ProductRepository(session)

    @staticmethod
    def _default_source(
        settings: ParsinaSettings | None, transport: BaseTransport | None
    ) -> CommoditySource:
        # Explicit settings/transport pin the live client (tests, production).
        if settings is not None or transport is not None:
            return ParsinaCommoditySource(settings or get_parsina_settings(), transport=transport)
        return build_commodity_source(
            app_settings=get_settings(),
            parsina_settings=get_parsina_settings(),
        )

    # ── PUBLIC ───────────────────────────────────────────────

    @property
    def source_label(self) -> SourceLabel:
        return self._source.label

    @property
    def configured(self) -> bool:
        return self._source.is_configured

    def acquire(self) -> None:
        """Take the cross-worker lock; only one manual/scheduled run may hold it."""
        # Busy wins over unconfigured: telling the user about the run in
        # progress is more useful than a config error while it finishes.
        if not self._sync_state.try_acquire(now=datetime.now(UTC), lock_seconds=LOCK_SECONDS):
            raise SyncBusyError("همگام‌سازی دیگری در حال اجراست")
        if not self._source.is_configured:
            # Release quietly: a missing config must not clobber the last real error.
            self._sync_state.release(success=True)
            raise SyncNotConfiguredError(self._not_configured_message())

    def run(self, *, replace: bool = False) -> SyncResult:
        self.acquire()
        return self.run_acquired(replace=replace)

    def run_acquired(self, *, replace: bool = False) -> SyncResult:
        """Fetch + validate + apply. Caller already holds the sync lock.

        `replace` drops the existing mirror first (dev CSV seeding only).
        """
        now = datetime.now(UTC)
        try:
            rows, units = self._fetch()
            result = self._apply(rows, units, now, replace=replace)
        except Exception as exc:  # noqa: BLE001 — record, then let the caller classify
            self._fail(now, exc)
            raise
        self._sync_state.record_result(
            attempted_at=now,
            processed=result.processed,
            created=result.created,
            updated=result.updated,
            deactivated=result.deactivated,
            skipped=result.skipped,
        )
        self._sync_state.release(success=True)
        log.info(
            "parsina sync ok: processed=%d created=%d updated=%d deactivated=%d skipped=%d",
            result.processed,
            result.created,
            result.updated,
            result.deactivated,
            result.skipped,
        )
        return result

    def state(self) -> ParsinaSyncState:
        return self._sync_state.get()

    def _not_configured_message(self) -> str:
        if self._source.label == "csv":
            return "فایل داده آزمایشی محصولات یافت نشد"
        if self._source.label == "dev":
            return "اتصال دیتابیس dev تنظیم نشده است"
        return "تنظیمات اتصال پارسینا کامل نیست"

    # ── FETCH / VALIDATE ─────────────────────────────────────

    def _fetch(self) -> tuple[list[CommodityRow], dict[int, str]]:
        raw_rows, reported_total, units = self._source.fetch()
        if reported_total is not None and reported_total != len(raw_rows):
            raise ParsinaResponseError(
                f"فهرست دریافتی ناقص است ({len(raw_rows)} از {reported_total} ردیف)"
            )
        if not raw_rows:
            raise ParsinaResponseError("منبع داده فهرست کالایی خالی برگرداند")
        return self._normalize(raw_rows), units

    def _normalize(self, raw_rows: list[object]) -> list[CommodityRow]:
        rows: list[CommodityRow] = []
        for raw in raw_rows:
            row = parse_commodity(raw)
            if row is not None:
                rows.append(row)
        if not rows:
            raise ParsinaResponseError("هیچ کالای معتبری در داده دریافتی یافت نشد")
        if len(rows) * 2 < len(raw_rows):
            raise ParsinaResponseError("بیشتر ردیف‌های داده دریافتی فاقد شناسه معتبر بودند")
        return rows

    # ── APPLY ────────────────────────────────────────────────

    def _apply(
        self,
        rows: list[CommodityRow],
        units: dict[int, str],
        now: datetime,
        *,
        replace: bool,
    ) -> SyncResult:
        if replace:
            removed = self._products.delete_all()
            self._session.flush()
            log.info("product catalog replaced: %d existing rows removed", removed)
        ids = {row.good_id for row in rows}
        existing = self._products.by_external_ids(ids)
        taken_skus = self._products.sku_in_use({row.good_code for row in rows})
        created = updated = skipped = 0
        for row in rows:
            product = existing.get(row.good_id)
            if product is None and row.good_code in taken_skus:
                # Legacy/smart rows own this SKU; skip rather than merge blindly.
                skipped += 1
                continue
            if product is None:
                product = Product(external_id=row.good_id, sku=row.good_code, name=row.good_name)
                self._session.add(product)
                created += 1
            else:
                updated += 1
            self._assign(product, row, units)
            product.synced_at = now
            product.is_active = True
        self._session.flush()
        # Flush first so newly-created rows carry their external_id, then prune.
        deactivated = self._products.deactivate_missing(ids)
        self._session.commit()
        return SyncResult(
            processed=len(rows),
            created=created,
            updated=updated,
            deactivated=deactivated,
            skipped=skipped,
        )

    def _assign(self, product: Product, row: CommodityRow, units: dict[int, str]) -> None:
        product.name = row.good_name
        product.sku = row.good_code
        product.price = _money(row.sale_price)
        product.stock = _stock(row)
        product.main_group_id = row.main_group
        product.sub_group_id = row.sub_group
        product.main_group_name = row.main_group_name
        product.sub_group_name = row.sub_group_name
        product.unit_id = row.count_unit
        product.unit_name = units.get(row.count_unit) if row.count_unit is not None else None
        product.weight = row.weight
        product.is_special = row.is_special
        product.buy_price = row.buy_price
        product.sale_pack_price = row.sale_pack_price
        product.sale_box_price = row.sale_box_price
        product.use_price = row.use_price
        product.discount = row.discount
        product.extra = row.extra
        product.number_in_box = row.number_in_box
        product.number_in_pack = row.number_in_pack
        product.ware_remain = row.ware_remain

    # ── FAILURE ──────────────────────────────────────────────

    def _fail(self, now: datetime, exc: Exception) -> None:
        self._session.rollback()
        message = self._describe(exc)
        self._sync_state.record_failure(attempted_at=now, error=message)
        self._sync_state.release(success=False, error=message)
        log.warning("product sync failed: %s", message)

    def _describe(self, exc: Exception) -> str:
        if isinstance(exc, CsvSourceError):
            return f"خطای داده آزمایشی: {exc}"
        if isinstance(exc, DevDbSourceError):
            return f"خطای دیتابیس dev: {exc}"
        if isinstance(exc, ParsinaAuthError):
            return f"خطای احراز هویت پارسینا: {exc}"
        if isinstance(exc, ParsinaNetworkError):
            return f"خطای ارتباط با پارسینا: {exc}"
        if isinstance(exc, ParsinaResponseError):
            if self._source.label == "csv":
                return f"داده آزمایشی نامعتبر است: {exc}"
            if self._source.label == "dev":
                return f"داده دیتابیس dev نامعتبر است: {exc}"
            return f"پاسخ نامعتبر پارسینا: {exc}"
        return f"خطای همگام‌سازی: {exc}"


def run_scheduled_sync(
    *,
    session_factory: Callable[[], Session],
    interval_minutes: int,
    transport: BaseTransport | None = None,
) -> SyncResult | None:
    """One scheduler tick: no-op unless production AND configured, enabled, due.

    With `DEV_DATABASE_URL` set, the tick copies the dev mirror (simulation);
    otherwise it requires Parsina credentials, same as the manual button.
    """
    if not get_settings().is_production:
        return None
    if get_settings().dev_database_url.strip():
        with session_factory() as session:
            last_attempt = SyncStateRepository(session).get().last_attempt_at
            if last_attempt is not None:
                if last_attempt.tzinfo is None:
                    last_attempt = last_attempt.replace(tzinfo=UTC)
                if datetime.now(UTC) < last_attempt + timedelta(minutes=interval_minutes):
                    return None
            try:
                return ProductSyncService(session, transport=transport).run()
            except SyncBusyError:
                return None
    settings = get_parsina_settings()
    if not settings.is_configured or not settings.parsina_sync_enabled:
        return None
    with session_factory() as session:
        last_attempt = SyncStateRepository(session).get().last_attempt_at
        if last_attempt is not None:
            if last_attempt.tzinfo is None:
                last_attempt = last_attempt.replace(tzinfo=UTC)
            if datetime.now(UTC) < last_attempt + timedelta(minutes=interval_minutes):
                return None
        try:
            return ProductSyncService(session, settings=settings, transport=transport).run()
        except SyncBusyError:
            return None


__all__ = [
    "LOCK_SECONDS",
    "SYNC_INTERVAL_MINUTES",
    "ProductSyncService",
    "SyncBusyError",
    "SyncNotConfiguredError",
    "SyncResult",
    "ParsinaAuthError",
    "ParsinaError",
    "ParsinaNetworkError",
    "ParsinaResponseError",
    "run_scheduled_sync",
]
