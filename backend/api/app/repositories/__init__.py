from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, *, query: str, page: int, page_size: int) -> tuple[list[Product], int]:
        base = select(Product)
        count_stmt = select(func.count()).select_from(Product)
        if query:
            base = base.where(Product.name.ilike(f"%{query}%"))
            count_stmt = count_stmt.where(Product.name.ilike(f"%{query}%"))
        total = self._session.execute(count_stmt).scalar_one()
        start = (page - 1) * page_size
        rows = (
            self._session.execute(base.order_by(Product.id.desc()).offset(start).limit(page_size))
            .scalars()
            .all()
        )
        return list(rows), total

    def add(self, product: Product) -> Product:
        self._session.add(product)
        self._session.flush()
        return product
