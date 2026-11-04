"""SQL access for manually managed competitor listings."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CompetitorListing, Product


class CompetitorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def product(self, product_id: int) -> Product | None:
        return self._session.get(Product, product_id)

    def list_for_product(self, product_id: int) -> list[CompetitorListing]:
        return list(
            self._session.execute(
                select(CompetitorListing)
                .where(CompetitorListing.product_id == product_id)
                .order_by(CompetitorListing.created_at)
            ).scalars()
        )

    def list_for_products(self, product_ids: set[int]) -> list[CompetitorListing]:
        if not product_ids:
            return []
        return list(
            self._session.execute(
                select(CompetitorListing)
                .where(
                    CompetitorListing.product_id.in_(product_ids),
                    CompetitorListing.is_active.is_(True),
                )
                .order_by(CompetitorListing.created_at)
            ).scalars()
        )

    def list_active(self) -> list[CompetitorListing]:
        return list(
            self._session.execute(
                select(CompetitorListing)
                .where(CompetitorListing.is_active.is_(True))
                .order_by(CompetitorListing.created_at)
            ).scalars()
        )

    def list_all(self) -> list[CompetitorListing]:
        return list(
            self._session.execute(
                select(CompetitorListing).order_by(CompetitorListing.created_at)
            ).scalars()
        )

    def get(self, listing_id: int) -> CompetitorListing | None:
        return self._session.get(CompetitorListing, listing_id)

    def get_by_product_store(
        self, product_id: int, store: str, exclude_id: int | None = None
    ) -> CompetitorListing | None:
        query = select(CompetitorListing).where(
            CompetitorListing.product_id == product_id,
            CompetitorListing.store == store,
        )
        if exclude_id is not None:
            query = query.where(CompetitorListing.id != exclude_id)
        return self._session.execute(query).scalars().first()

    def add(self, listing: CompetitorListing) -> CompetitorListing:
        self._session.add(listing)
        self._session.flush()
        return listing

    def delete(self, listing: CompetitorListing) -> None:
        self._session.delete(listing)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()
