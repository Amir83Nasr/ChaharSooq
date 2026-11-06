"""Dashboard service — overview, competitor gaps, and catalog breakdown."""

import re
from datetime import UTC, datetime, timedelta
from typing import TypedDict

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories import ProductRepository
from app.schemas import (
    CatalogBrandOut,
    CatalogSectionOut,
    CompetitorGapOut,
    DashboardGroupOut,
    DashboardOverviewOut,
    DashboardSummaryOut,
)

TOP_GROUPS_LIMIT = 6

SECTION_ORDER = ("فرش", "مبلمان", "لوازم خانگی", "سایر")


class _BrandBucket(TypedDict):
    brand: str
    count: int
    stock_value: int


def top_group_of(name: str | None) -> str | None:
    """Mirror of the products table `topGroupOf` — section (بخش) per group."""
    if not name:
        return None
    text = name.strip()
    if not text:
        return None
    if text.startswith("فرش"):
        return "فرش"
    if text.startswith("مبلمان"):
        return "مبلمان"
    return "لوازم خانگی"


def brand_of(name: str | None, top: str | None) -> str | None:
    """Mirror of the products table `brandOf` — remainder after the prefix."""
    if not name:
        return None
    text = name.strip()
    if not text:
        return None
    if top == "فرش":
        rest = text.removeprefix("فرش").strip()
        return rest or None
    if top == "مبلمان":
        rest = text.removeprefix("مبلمان").strip()
        return rest or None
    if top == "لوازم خانگی":
        rest = re.sub(r"^لوازم\s+خان[گک]ی\s*", "", text).strip()
        return rest or text
    return text


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
        coverage, appliance_total = self._products.coverage_and_appliance_total(
            since=self._price_since()
        )
        return DashboardOverviewOut(
            total=summary["total"],
            in_stock=summary["in_stock"],
            low=summary["low"],
            out=summary["out"],
            stock_value=summary["stock_value"],
            competitor_coverage=coverage,
            appliance_total=appliance_total,
            groups=groups,
        )

    def summary(self, *, low_stock_threshold: int, gap_limit: int) -> DashboardSummaryOut:
        """One-call dashboard payload — 4 round-trips instead of 3×N fetches."""
        overview = self.overview(low_stock_threshold=low_stock_threshold)
        if overview.total == 0:
            # Empty catalog: skip the gap/catalog scans entirely.
            return DashboardSummaryOut(overview=overview, gaps=[], catalog=[])
        return DashboardSummaryOut(
            overview=overview,
            gaps=self.competitor_gaps(limit=gap_limit),
            catalog=self.catalog_breakdown(),
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

    def catalog_breakdown(self) -> list[CatalogSectionOut]:
        """Per-section (بخش) brand stats — items, groups, brands, stock value.

        Groups are raw `main_group_name` values; blank/`NULL` collapses to
        "سایر" so ungrouped rows are never lost. Brands follow the products
        table remainder rule, so counts match what the table shows.
        """
        buckets: dict[str, dict[str, _BrandBucket]] = {}
        for raw_name, count, stock_value in self._products.catalog_breakdown():
            top = top_group_of(raw_name) or "سایر"
            display_group = (raw_name or "").strip() or "سایر"
            brand = brand_of(raw_name, top if top != "سایر" else None) or "سایر"
            section = buckets.setdefault(top, {})
            entry = section.setdefault(
                display_group, {"brand": brand, "count": 0, "stock_value": 0}
            )
            entry["count"] += count
            entry["stock_value"] += stock_value
        sections: list[CatalogSectionOut] = []
        for top in SECTION_ORDER:
            groups = buckets.get(top, {})
            brands = sorted(
                (
                    CatalogBrandOut(
                        group_name=group_name,
                        brand=entry["brand"],
                        count=entry["count"],
                        stock_value=entry["stock_value"],
                    )
                    for group_name, entry in groups.items()
                ),
                key=lambda b: (-b.count, b.group_name),
            )
            sections.append(
                CatalogSectionOut(
                    top_group=top,
                    items=sum(b.count for b in brands),
                    group_count=len(brands),
                    brand_count=len({b.brand for b in brands}),
                    stock_value=sum(b.stock_value for b in brands),
                    brands=brands,
                )
            )
        return sections
