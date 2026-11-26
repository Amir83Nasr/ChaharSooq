"""Product analysis report repository — direct queries only."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.analysis import ProductAnalysisReport


class ProductAnalysisReportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, product_id: int) -> ProductAnalysisReport | None:
        return self._session.get(ProductAnalysisReport, product_id)

    def upsert(
        self,
        product_id: int,
        *,
        content: str,
        model_id: str,
        generated_at: datetime,
    ) -> ProductAnalysisReport:
        row = self.get(product_id)
        if row is None:
            row = ProductAnalysisReport(
                product_id=product_id,
                content=content,
                model_id=model_id,
                generated_at=generated_at,
            )
            self._session.add(row)
        else:
            row.content = content
            row.model_id = model_id
            row.generated_at = generated_at
        self._session.flush()
        return row

    def delete(self, product_id: int) -> bool:
        row = self.get(product_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True
