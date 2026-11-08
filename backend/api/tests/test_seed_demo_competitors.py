"""Dev demo seed fills the products table and stays idempotent."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import (
    CompetitorListing,
    CompetitorPriceObservation,
    Product,
    SuggestedPriceFormula,
)
from scripts.seed_demo_competitors import seed_demo_competitors

NOW = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def _session(path: Path) -> Session:
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return Session(engine)


def _product(name: str, group: str, price: int) -> Product:
    return Product(
        name=name,
        sku=name,
        price=Decimal(price),
        stock=Decimal(1),
        main_group_name=group,
    )


def _all(session: Session, model: type) -> list:
    return list(session.scalars(select(model)))


def test_seed_fills_every_group_and_refreshes_only_demo_rows(tmp_path: Path) -> None:
    with _session(tmp_path / "demo.db") as session:
        appliance = _product("یخچال", "لوازم خانگی دوو", 10_000_000)
        sofa = _product("مبل", "مبلمان", 20_000_000)
        carpet = _product("فرش", "فرش آدینا", 30_000_000)
        manual = _product("دستی", "لوازم خانگی سام", 40_000_000)
        session.add_all([appliance, sofa, carpet, manual])
        session.flush()
        session.add(
            CompetitorListing(
                product_id=manual.id,
                store="digikala",
                url="https://www.digikala.com/product/dkp-1/",
            )
        )
        session.add(SuggestedPriceFormula(top_group="لوازم خانگی", weight=Decimal("0.2000")))
        session.commit()

        result = seed_demo_competitors(session, now=NOW)
        assert result.created == 4  # two appliance stores + sofa + digifresh
        assert result.refreshed == 4
        assert result.observations == 8  # today + yesterday per demo listing
        assert result.weights == 2  # فرش and مبلمان; the appliance weight stays
        assert result.bounds == 6  # floor + ceiling for the three demo products

        listings = _all(session, CompetitorListing)
        demo = [row for row in listings if "/product/demo-" in row.url]
        assert len(demo) == 4
        assert {row.store for row in demo} == {"digikala", "technolife", "sofa", "digifresh"}
        assert all(row.status == "success" and row.fetched_price for row in demo)
        assert all(row.fetched_currency == "IRT" for row in demo)

        observations = _all(session, CompetitorPriceObservation)
        assert len(observations) == 8
        assert {row.observed_at.date() for row in observations} == {
            NOW.date(),
            (NOW - timedelta(days=1)).date(),
        }
        assert all(row.price > 0 for row in observations)

        for demo_product in (appliance, sofa, carpet):
            session.refresh(demo_product)
            assert demo_product.allowed_decrease_percent is not None
            assert demo_product.allowed_increase_percent is not None
            assert Decimal(5) <= demo_product.allowed_decrease_percent <= Decimal(15)
            assert Decimal(8) <= demo_product.allowed_increase_percent <= Decimal(18)
        session.refresh(manual)
        assert manual.allowed_decrease_percent is None
        assert manual.allowed_increase_percent is None

        manual_listing = session.scalar(
            select(CompetitorListing).where(CompetitorListing.product_id == manual.id)
        )
        assert manual_listing is not None
        assert manual_listing.fetched_price is None
        assert manual_listing.status == "pending"

        # An admin's saved bound survives a re-run.
        appliance.allowed_decrease_percent = Decimal("3")
        session.commit()

        # A second run refreshes freshness without duplicating rows.
        again = seed_demo_competitors(session, now=NOW)
        assert again.created == 0
        assert again.refreshed == 4
        assert again.observations == 0
        assert again.weights == 0
        assert again.bounds == 0
        session.refresh(appliance)
        assert appliance.allowed_decrease_percent == Decimal("3")
        assert len(_all(session, CompetitorListing)) == 5
        assert len(_all(session, CompetitorPriceObservation)) == 8

        weights = {row.top_group: row.weight for row in _all(session, SuggestedPriceFormula)}
        assert weights == {
            "لوازم خانگی": Decimal("0.2000"),
            "فرش": Decimal("0.4000"),
            "مبلمان": Decimal("0.5000"),
        }
