from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, *, query: str, page: int, page_size: int) -> tuple[list[Product], int]:
        stmt = select(Product).order_by(Product.id.desc())
        if query:
            stmt = stmt.where(Product.name.ilike(f"%{query}%"))
        rows = self._session.execute(stmt).scalars().all()
        total = len(rows)
        start = (page - 1) * page_size
        return list(rows[start : start + page_size]), total

    def add(self, product: Product) -> Product:
        self._session.add(product)
        self._session.flush()
        return product
