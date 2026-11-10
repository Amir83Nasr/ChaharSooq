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
from scripts.seed_demo_competitors import (
    TARGET_WEIGHTS,
    demo_bounds,
    demo_prices,
    demo_scenario,
    seed_demo_competitors,
)

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


def _product_for_scenario(scenario: str, group: str, price: int, *, prefix: str = "p") -> Product:
    """Product whose stable SKU key lands in the requested demo scenario."""
    for suffix in range(10_000):
        product = _product(f"{prefix}-{scenario}-{suffix}", group, price)
        if demo_scenario(product) == scenario:
            return product
    raise AssertionError(f"no SKU produced scenario {scenario!r}")


def _all(session: Session, model: type) -> list:
    return list(session.scalars(select(model)))


def test_seed_fills_every_group_and_refreshes_only_demo_rows(tmp_path: Path) -> None:
    with _session(tmp_path / "demo.db") as session:
        appliance = _product_for_scenario("floor", "لوازم خانگی دوو", 10_000_000)
        sofa = _product_for_scenario("ceiling", "مبلمان", 20_000_000)
        carpet = _product_for_scenario("inside", "فرش آدینا", 30_000_000)
        unbounded = _product_for_scenario("no_bounds", "لوازم خانگی سام", 50_000_000)
        manual = _product("دستی", "لوازم خانگی سام", 40_000_000)
        session.add_all([appliance, sofa, carpet, unbounded, manual])
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
        assert result.created == 6  # two appliance stores each for two rows + sofa + digifresh
        assert result.refreshed == 6
        assert result.observations == 12  # today + yesterday per demo listing
        assert result.weights == 2  # فرش and مبلمان; the appliance weight stays
        assert result.bounds == 6  # tight floor+ceiling for two rows, loose pair for one

        listings = _all(session, CompetitorListing)
        demo = [row for row in listings if "/product/demo-" in row.url]
        assert len(demo) == 6
        assert {row.store for row in demo} == {"digikala", "technolife", "sofa", "digifresh"}
        assert all(row.status == "success" and row.fetched_price for row in demo)
        assert all(row.fetched_currency == "IRT" for row in demo)

        observations = _all(session, CompetitorPriceObservation)
        assert len(observations) == 12
        assert {row.observed_at.date() for row in observations} == {
            NOW.date(),
            (NOW - timedelta(days=1)).date(),
        }
        assert all(row.price > 0 for row in observations)

        # Every scenario is requested explicitly, so the clamp assertions are
        # independent of database insertion order.
        for demo_product in (appliance, sofa):
            session.refresh(demo_product)
            assert demo_product.allowed_decrease_percent == Decimal("1.50")
            assert demo_product.allowed_increase_percent == Decimal("1.50")
        session.refresh(carpet)
        carpet_decrease = carpet.allowed_decrease_percent
        carpet_increase = carpet.allowed_increase_percent
        assert carpet_decrease is not None
        assert carpet_increase is not None
        assert Decimal(5) <= carpet_decrease <= Decimal(15)
        assert Decimal(8) <= carpet_increase <= Decimal(18)
        session.refresh(unbounded)
        assert unbounded.allowed_decrease_percent is None
        assert unbounded.allowed_increase_percent is None
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

        # A second run refreshes demo history in place (no duplicated rows).
        again = seed_demo_competitors(session, now=NOW)
        assert again.created == 0
        assert again.refreshed == 6
        assert again.observations == 12  # yesterday + today rewritten
        assert again.weights == 0
        assert again.bounds == 0
        session.refresh(appliance)
        assert appliance.allowed_decrease_percent == Decimal("3")
        assert len(_all(session, CompetitorListing)) == 7
        assert len(_all(session, CompetitorPriceObservation)) == 12

        weights = {row.top_group: row.weight for row in _all(session, SuggestedPriceFormula)}
        assert weights == {
            "لوازم خانگی": Decimal("0.2000"),
            "فرش": Decimal("0.4000"),
            "مبلمان": Decimal("0.5000"),
        }


def test_demo_rows_cover_every_suggested_price_clamp_branch(tmp_path: Path) -> None:
    """Demo data must land below the floor, above the ceiling, and inside."""
    with _session(tmp_path / "scenarios.db") as session:
        appliance = _product_for_scenario("floor", "لوازم خانگی دوو", 10_000_000)
        sofa = _product_for_scenario("ceiling", "مبلمان", 20_000_000)
        carpet = _product_for_scenario("inside", "فرش آدینا", 30_000_000)
        session.add_all([appliance, sofa, carpet])
        session.commit()
        seed_demo_competitors(session, now=NOW)
        for product in (appliance, sofa, carpet):
            session.refresh(product)

        assert demo_scenario(appliance) == "floor"
        assert demo_scenario(sofa) == "ceiling"
        assert demo_scenario(carpet) == "inside"

        # Appliances blend the competitor price; furniture/carpet use the link's
        # daily change. Mirror the frontend formula to check the seed's intent.
        appliance_base = appliance.price
        appliance_price, _ = demo_prices(appliance, "digikala")
        appliance_weight = TARGET_WEIGHTS["لوازم خانگی"]
        appliance_raw = appliance_weight * appliance_price + (1 - appliance_weight) * appliance_base
        appliance_floor = appliance_base * (1 - Decimal("1.50") / 100)
        assert appliance_raw < appliance_floor

        sofa_base = sofa.price
        _, sofa_change = demo_prices(sofa, "sofa")
        sofa_weight = TARGET_WEIGHTS["مبلمان"]
        sofa_raw = sofa_base * (1 + sofa_weight * sofa_change / 100)
        sofa_ceiling = sofa_base * (1 + Decimal("1.50") / 100)
        assert sofa_raw > sofa_ceiling

        carpet_base = carpet.price
        _, carpet_change = demo_prices(carpet, "digifresh")
        carpet_weight = TARGET_WEIGHTS["فرش"]
        carpet_raw = carpet_base * (1 + carpet_weight * carpet_change / 100)
        decrease, increase = demo_bounds(carpet)
        assert carpet_base * (1 - decrease / 100) <= carpet_raw
        assert carpet_raw <= carpet_base * (1 + increase / 100)


def test_demo_values_do_not_depend_on_database_ids() -> None:
    """Dev and staging store the same catalog row under different ids."""

    def row(primary_key: int, external_id: int) -> Product:
        return Product(
            id=primary_key,
            external_id=external_id,
            name="یخچال",
            sku="SKU-1",
            price=Decimal(10_000_000),
            stock=Decimal(1),
            main_group_name="لوازم خانگی",
        )

    dev_row = row(7, 1234)
    staging_row = row(91, 1234)

    assert demo_scenario(dev_row) == demo_scenario(staging_row)
    assert demo_bounds(dev_row) == demo_bounds(staging_row)
    for store in ("digikala", "technolife", "sofa", "digifresh"):
        assert demo_prices(dev_row, store) == demo_prices(staging_row, store)
