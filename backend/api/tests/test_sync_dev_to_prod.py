"""Dev → prod copy must be additive: ids and competitor links survive."""

from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import Category, CompetitorListing, Product, Setting
from scripts.sync_dev_to_prod import _safe_url, sync


def _database(path: Path) -> str:
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


def _seed_dev(url: str) -> None:
    with Session(create_engine(url)) as session:
        category = Category(name="لوازم خانگی")
        session.add(category)
        session.flush()
        product = Product(
            external_id=1,
            name="یخچال",
            sku="FRIDGE-1",
            price=Decimal(100),
            stock=Decimal(2),
            category_id=category.id,
            allowed_decrease_percent=Decimal(7),
            allowed_increase_percent=Decimal(12),
        )
        session.add(product)
        session.flush()
        session.add(
            CompetitorListing(
                product_id=product.id,
                store="digikala",
                url="https://www.digikala.com/product/dkp-1/",
            )
        )
        # Demo rows are dev-only and must never be copied into production.
        session.add(
            CompetitorListing(
                product_id=product.id,
                store="other",
                url="https://example.com/product/demo-1/",
            )
        )
        session.add(Setting(key="low_stock_threshold", value="4"))
        session.commit()


def _seed_prod(url: str) -> None:
    with Session(create_engine(url)) as session:
        category = Category(name="لوازم خانگی")
        session.add(category)
        session.flush()
        # A prod-only manual row keeps its id and must not be pruned.
        session.add(Product(name="دستی", sku="MANUAL-1", price=Decimal(1), stock=Decimal(1)))
        product = Product(
            external_id=1,
            name="نام قدیمی",
            sku="FRIDGE-1",
            price=Decimal(90),
            stock=Decimal(1),
            category_id=category.id,
            # Bounds are per-environment admin settings; the sync must not
            # overwrite them with the dev values.
            allowed_decrease_percent=Decimal(4),
            allowed_increase_percent=Decimal(9),
        )
        session.add(product)
        session.flush()
        session.add(
            CompetitorListing(
                product_id=product.id,
                store="technolife",
                url="https://www.technolife.com/product-1/",
            )
        )
        session.add(Setting(key="low_stock_threshold", value="2"))
        session.commit()


def test_sync_upserts_products_and_keeps_existing_links(tmp_path: Path) -> None:
    dev_url = _database(tmp_path / "dev.db")
    prod_url = _database(tmp_path / "prod.db")
    _seed_dev(dev_url)
    _seed_prod(prod_url)

    with Session(create_engine(prod_url)) as session:
        product = session.scalar(select(Product).where(Product.external_id == 1))
        assert product is not None
        product_id = product.id
        category_id = product.category_id
        manual_id = session.scalar(select(Product.id).where(Product.sku == "MANUAL-1"))

    counts = sync(dev_url, prod_url)
    assert counts == {
        "categories": 1,
        "settings": 1,
        "products": 1,
        "competitor_listings_added": 1,
    }

    with Session(create_engine(prod_url)) as session:
        product = session.scalar(select(Product).where(Product.external_id == 1))
        assert product is not None
        assert product.id == product_id
        assert product.name == "یخچال"
        assert product.category_id == category_id
        assert product.allowed_decrease_percent == Decimal(4)
        assert product.allowed_increase_percent == Decimal(9)
        assert session.get(Product, manual_id) is not None

        links = session.scalars(
            select(CompetitorListing).where(CompetitorListing.product_id == product_id)
        ).all()
        assert {link.store for link in links} == {"digikala", "technolife"}
        digikala = next(link for link in links if link.store == "digikala")
        assert digikala.url == "https://www.digikala.com/product/dkp-1/"

        setting = session.get(Setting, "low_stock_threshold")
        assert setting is not None and setting.value == "4"

    # A second run is idempotent: no duplicate links, no id changes.
    assert sync(dev_url, prod_url)["competitor_listings_added"] == 0
    with Session(create_engine(prod_url)) as session:
        product = session.scalar(select(Product).where(Product.external_id == 1))
        assert product is not None and product.id == product_id
        assert (
            len(
                session.scalars(
                    select(CompetitorListing).where(CompetitorListing.product_id == product_id)
                ).all()
            )
            == 2
        )


def test_confirmation_url_hides_password() -> None:
    rendered = _safe_url(
        "postgresql+psycopg://user:super-secret@db.example.com/neondb?sslmode=require"
    )
    assert "super-secret" not in rendered
    assert "user" in rendered
    assert "db.example.com" in rendered
