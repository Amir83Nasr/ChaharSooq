"""Product sources — dev CSV fixture and environment-based source selection."""

import csv
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ParsinaSettings, Settings
from app.core.database import get_engine
from app.integrations.parsina import parse_commodity
from app.integrations.parsina_csv import CsvCommoditySource, CsvSourceError
from app.integrations.sources import ParsinaCommoditySource, build_commodity_source
from app.models import Product
from app.services.sync import ProductSyncService

FIELDS = [
    "goodId",
    "goodCode",
    "goodName",
    "mainGroup",
    "subGroup",
    "mainGroupName",
    "subGroupName",
    "countUnit",
    "weight",
    "khas",
    "salePackPrice",
    "saleBoxPrice",
    "usePrice",
    "discount",
    "extra",
    "numberInBox",
    "numberInPack",
    "buyPrice",
    "salePrice",
    "remain",
    "wareRemain",
]

FIXTURE = Path(__file__).resolve().parents[3] / "data" / "parsina-products.csv"


def _row(
    good_id: str,
    code: str,
    name: str,
    *,
    sale: str = "1000",
    remain: str = "3",
    special: str = "false",
    unit: str = "4",
) -> dict[str, str]:
    return {
        "goodId": good_id,
        "goodCode": code,
        "goodName": name,
        "mainGroup": "1",
        "subGroup": "2",
        "mainGroupName": "گروه اصلی",
        "subGroupName": "زیرگروه",
        "countUnit": unit,
        "weight": "1.5",
        "khas": special,
        "salePackPrice": "1000",
        "saleBoxPrice": "1000",
        "usePrice": "1000",
        "discount": "0",
        "extra": "0",
        "numberInBox": "1",
        "numberInPack": "1",
        "buyPrice": "900",
        "salePrice": sale,
        "remain": remain,
        "wareRemain": remain,
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    """Mirror the export: BOM, padded headers and padded values."""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([f" {name} " for name in FIELDS])
        for row in rows:
            writer.writerow([f" {row.get(name, '')} " for name in FIELDS])
    return path


@pytest.fixture()
def session(client: TestClient) -> Iterator[Session]:
    """Depends on `client` so the in-memory schema exists before use."""
    with Session(get_engine()) as s:
        yield s


# ── SOURCE ───────────────────────────────────────────────────


def test_csv_source_strips_padding_and_parses_rows(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "products.csv",
        [
            _row("1", "A-1", "کالا یک", special="false"),
            _row("2", "A-2", "کالا دو", special="true"),
        ],
    )
    source = CsvCommoditySource(path)
    assert source.is_configured
    raw_rows, total, units = source.fetch()

    assert total == len(raw_rows) == 2
    # The export only has countUnit ids; the source supplies the dev titles.
    assert units == {4: "عدد"}
    assert raw_rows[0]["goodCode"] == "A-1"
    assert raw_rows[0]["goodName"] == "کالا یک"

    first = parse_commodity(raw_rows[0])
    second = parse_commodity(raw_rows[1])
    assert first is not None and second is not None
    assert first.good_id == 1
    assert first.is_special is False
    assert second.is_special is True
    assert first.sale_price == Decimal("1000")
    assert first.remain == Decimal("3")


def test_csv_source_missing_file_is_not_configured(tmp_path: Path) -> None:
    assert CsvCommoditySource(tmp_path / "missing.csv").is_configured is False


def test_csv_source_reports_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(CsvSourceError):
        CsvCommoditySource(path).fetch()


def test_csv_source_titles_unknown_units(tmp_path: Path) -> None:
    """A new unit id must still produce a title, never an empty cell."""
    path = _write_csv(tmp_path / "products.csv", [_row("1", "A-1", "کالا", unit="99")])
    _, _, units = CsvCommoditySource(path).fetch()
    assert units == {99: "عدد"}


@pytest.mark.skipif(not FIXTURE.exists(), reason="local Parsina CSV fixture not present")
def test_real_fixture_parses_completely() -> None:
    raw_rows, total, units = CsvCommoditySource(FIXTURE).fetch()

    assert total == len(raw_rows)
    assert len(raw_rows) > 1000
    parsed = [parse_commodity(row) for row in raw_rows]
    assert all(row is not None for row in parsed)
    assert len({row.good_id for row in parsed if row is not None}) == len(parsed)
    # Every unit referenced by a row has a title, like the production units call.
    referenced = {row.count_unit for row in parsed if row is not None and row.count_unit}
    assert referenced
    assert referenced <= set(units)
    assert all(units[unit_id] for unit_id in referenced)


# ── SELECTION ────────────────────────────────────────────────


def test_development_selects_csv_source() -> None:
    source = build_commodity_source(
        app_settings=Settings(app_env="development"),
        parsina_settings=ParsinaSettings(),
    )
    assert isinstance(source, CsvCommoditySource)


def test_production_selects_parsina_source() -> None:
    source = build_commodity_source(
        app_settings=Settings(app_env="production"),
        parsina_settings=ParsinaSettings(),
    )
    assert isinstance(source, ParsinaCommoditySource)


def test_explicit_settings_pin_parsina_source(session: Session) -> None:
    service = ProductSyncService(session, settings=ParsinaSettings())
    assert service.source_label == "parsina"
    assert service.configured is False


# ── SYNC ─────────────────────────────────────────────────────


def test_csv_sync_inserts_then_updates(session: Session, tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "products.csv",
        [_row("1", "A-1", "کالا یک"), _row("2", "A-2", "کالا دو")],
    )
    source = CsvCommoditySource(path)

    first = ProductSyncService(session, source=source).run()
    assert (first.created, first.updated, first.processed) == (2, 0, 2)

    second = ProductSyncService(session, source=source).run()
    assert (second.created, second.updated, second.processed) == (0, 2, 2)

    products = session.execute(select(Product)).scalars().all()
    assert len(products) == 2
    assert {p.external_id for p in products} == {1, 2}
    assert {p.main_group_name for p in products} == {"گروه اصلی"}
    assert {p.unit_name for p in products} == {"عدد"}


def test_csv_sync_replace_drops_existing_catalog(session: Session, tmp_path: Path) -> None:
    session.add(Product(name="دستی", sku="MANUAL-1", price=Decimal(1), stock=Decimal(1)))
    session.commit()
    path = _write_csv(tmp_path / "products.csv", [_row("1", "A-1", "کالا یک")])

    result = ProductSyncService(session, source=CsvCommoditySource(path)).run(replace=True)

    assert result.created == 1
    rows = session.execute(select(Product)).scalars().all()
    assert len(rows) == 1
    assert rows[0].external_id == 1
