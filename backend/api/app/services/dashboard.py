"""Dashboard service — overview, competitor gaps, and attention aggregates."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories import ProductRepository
from app.schemas import (
    AttentionItemOut,
    AttentionOut,
    CompetitorGapOut,
    DashboardGroupOut,
    DashboardOverviewOut,
)

TOP_GROUPS_LIMIT = 6


class DashboardService:
    def __init__(self, session: Session) -> None:
        self._products = ProductRepository(session)

    def _price_since(self) -> datetime:
        return datetime.now(UTC) - timedelta(hours=get_settings().competitor_price_ttl_hours)

    def overview(self, *, low_stock_threshold: int) -> DashboardOverviewOut:
        summary = self._products.summary(low_stock_threshold=low_stock_threshold)
        groups = [
            DashboardGroupOut(name=name, count=count, stock_value=stock_value)
            for name, count, stock_value in self._products.stock_by_group(limit=TOP_GROUPS_LIMIT)
        ]
        coverage = self._products.competitor_coverage(since=self._price_since())
        return DashboardOverviewOut(
            total=summary["total"],
            in_stock=summary["in_stock"],
            low=summary["low"],
            out=summary["out"],
            stock_value=summary["stock_value"],
            competitor_coverage=coverage,
            groups=groups,
        )

    def competitor_gaps(self, *, limit: int) -> list[CompetitorGapOut]:
        """Biggest our-vs-competitor price differences, cheapest listing wins.

        Positive `diff_percent` means we are pricier than the competitor.
        """
        best: dict[int, CompetitorGapOut] = {}
        for row in self._products.competitor_gap_rows(since=self._price_since()):
            if row.competitor_price <= 0:
                continue
            diff = (row.our_price - row.competitor_price) / row.competitor_price * 100
            current = best.get(row.product_id)
            candidate = CompetitorGapOut(
                product_id=row.product_id,
                name=row.name,
                our_price=int(row.our_price),
                competitor_price=int(row.competitor_price),
                competitor_store=row.store,
                diff_percent=round(diff, 1),
            )
            if current is None or abs(diff) > abs(current.diff_percent):
                best[row.product_id] = candidate
        ranked = sorted(best.values(), key=lambda g: abs(g.diff_percent), reverse=True)
        return ranked[: max(limit, 1)]

    def attention(self, *, low_stock_threshold: int, limit: int) -> AttentionOut:
        out_rows, low_rows = self._products.attention_items(
            low_stock_threshold=low_stock_threshold, limit=limit
        )
        return AttentionOut(
            out=[
                AttentionItemOut(
                    product_id=r.product_id,
                    name=r.name,
                    price=int(r.price),
                    stock=r.stock,
                )
                for r in out_rows
            ],
            low=[
                AttentionItemOut(
                    product_id=r.product_id,
                    name=r.name,
                    price=int(r.price),
                    stock=r.stock,
                )
                for r in low_rows
            ],
        )
