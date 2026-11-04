"""Product sources — dev CSV fixture, dev DB simulation, source selection."""

import csv
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import ParsinaSettings, Settings
from app.core.database import Base, get_engine
from app.integrations.dev_db import (
    DevDatabaseCommoditySource,
    DevDbSourceError,
)
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

FIXTURE = Path(__file__).resolve().parents[3] / "data" / "parsina.csv"


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


def test_csv_source_strips_padding_parses_rows_and_titles_units(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "products.csv",
        [
            _row("1", "A-1", "کالا یک", special="false"),
            _row("2", "A-2", "کالا دو", special="true", unit="99"),
        ],
    )
    source = CsvCommoditySource(path)
    assert source.is_configured
    raw_rows, total, units = source.fetch()

    assert total == len(raw_rows) == 2
    # The export only has countUnit ids; the source supplies the dev titles.
    assert units == {4: "عدد", 99: "عدد"}
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


def test_csv_source_missing_or_unreadable_is_handled(tmp_path: Path) -> None:
    assert CsvCommoditySource(tmp_path / "missing.csv").is_configured is False
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(CsvSourceError):
        CsvCommoditySource(bad).fetch()


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


def test_source_selection_by_environment(tmp_path: Path) -> None:
    assert isinstance(
        build_commodity_source(
            app_settings=Settings(app_env="development"),
            parsina_settings=ParsinaSettings(),
        ),
        CsvCommoditySource,
    )
    assert isinstance(
        build_commodity_source(
            app_settings=Settings(app_env="production"),
            parsina_settings=ParsinaSettings(),
        ),
        ParsinaCommoditySource,
    )
    url = f"sqlite:///{tmp_path / 'dev.db'}"
    dev = build_commodity_source(
        app_settings=Settings(app_env="production", dev_database_url=url),
        parsina_settings=ParsinaSettings(),
    )
    assert isinstance(dev, DevDatabaseCommoditySource)
    assert dev.label == "dev" and dev.is_configured is True


def _make_dev_db(path: Path) -> str:
    """Separate sqlite file acting as the dev product mirror."""
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(
            Product(
                external_id=1,
                name="کالا یک",
                sku="A-1",
                price=Decimal(1000),
                stock=Decimal(3),
                main_group_name="گروه اصلی",
                unit_id=4,
                unit_name="عدد",
            )
        )
        s.add(
            Product(
                external_id=2,
                name="کالا دو",
                sku="A-2",
                price=Decimal(2000),
                stock=Decimal(5),
                main_group_name="گروه اصلی",
                unit_id=4,
                unit_name="عدد",
            )
        )
        s.commit()
    engine.dispose()
    return url


def test_dev_db_source_fetch_returns_parsina_shaped_rows(tmp_path: Path) -> None:
    url = _make_dev_db(tmp_path / "dev.db")
    raw_rows, total, units = DevDatabaseCommoditySource(url).fetch()

    assert total == len(raw_rows) == 2
    assert units == {4: "عدد"}
    row = parse_commodity(raw_rows[0])
    assert row is not None
    assert row.good_id in {1, 2}
    assert row.sale_price in {Decimal(1000), Decimal(2000)}


def test_dev_db_source_reports_unreachable_db(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'missing-dir' / 'dev.db'}"
    with pytest.raises(DevDbSourceError):
        DevDatabaseCommoditySource(url).fetch()


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


# ── DEV-DB SYNC ──────────────────────────────────────────────


def test_dev_db_sync_deactivates_rows_removed_from_dev(session: Session, tmp_path: Path) -> None:
    db_path = tmp_path / "dev.db"
    url = _make_dev_db(db_path)
    ProductSyncService(session, source=DevDatabaseCommoditySource(url)).run()

    engine = create_engine(url)
    with Session(engine) as s:
        victim = s.execute(select(Product).where(Product.external_id == 2)).scalar_one()
        s.delete(victim)
        s.commit()
    engine.dispose()

    result = ProductSyncService(session, source=DevDatabaseCommoditySource(url)).run()
    assert result.deactivated == 1
    session.expire_all()
    rows = {p.external_id: p for p in session.execute(select(Product)).scalars()}
    assert rows[1] is not None and rows[1].is_active
    assert rows[2] is not None and not rows[2].is_active
