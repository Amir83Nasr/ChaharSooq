"""Seed home-appliance products — idempotent, safe to re-run.

Machine-readable values only (integer toman, plain SKUs).
Persian display formatting happens in the UI.
Run via `make db-seed-products` from the repository root.

Re-run prunes products/categories absent from this file, so old
seed data (e.g. the previous grocery catalog) gets replaced.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base, get_engine
from app.models import Category, Product

CATEGORIES: list[str] = [
    "تلویزیون و صوتی‌تصویری",
    "یخچال و فریزر",
    "شست‌وشو و نظافت",
    "پخت‌وپز",
    "سرمایش و گرمایش",
    "مبلمان و دکوراسیون",
    "لوازم برقی آشپزخانه",
    "روشنایی",
]

# ponytail: prefix map covers current seed SKUs; new prefixes fall back to لوازم برقی آشپزخانه.
PREFIX_CATEGORY: dict[str, str] = {
    "TV": "تلویزیون و صوتی‌تصویری",
    "SND": "تلویزیون و صوتی‌تصویری",
    "FR": "یخچال و فریزر",
    "WASH": "شست‌وشو و نظافت",
    "DISH": "شست‌وشو و نظافت",
    "VAC": "شست‌وشو و نظافت",
    "IRON": "شست‌وشو و نظافت",
    "GAS": "پخت‌وپز",
    "OVEN": "پخت‌وپز",
    "MW": "پخت‌وپز",
    "FRY": "پخت‌وپز",
    "AC": "سرمایش و گرمایش",
    "HEAT": "سرمایش و گرمایش",
    "AIR": "سرمایش و گرمایش",
    "SOFA": "مبلمان و دکوراسیون",
    "TABLE": "مبلمان و دکوراسیون",
    "BED": "مبلمان و دکوراسیون",
    "FOOD": "لوازم برقی آشپزخانه",
    "MEAT": "لوازم برقی آشپزخانه",
    "JUICE": "لوازم برقی آشپزخانه",
    "KETTLE": "لوازم برقی آشپزخانه",
    "COFFEE": "لوازم برقی آشپزخانه",
    "TOAST": "لوازم برقی آشپزخانه",
    "MIX": "لوازم برقی آشپزخانه",
    "LUST": "روشنایی",
    "LAMP": "روشنایی",
}

PRODUCTS: list[dict[str, str | int]] = [
    # ── TV / SOUND ──
    {"name": "تلویزیون ۵۵ اینچ 4K هوشمند", "sku": "TV-001", "price": 32000000, "stock": 12},
    {"name": "تلویزیون ۶۵ اینچ QLED", "sku": "TV-002", "price": 58000000, "stock": 7},
    {"name": "تلویزیون ۵۰ اینچ 4K", "sku": "TV-003", "price": 26500000, "stock": 15},
    {"name": "تلویزیون ۴۳ اینچ فول‌اچ‌دی", "sku": "TV-004", "price": 17800000, "stock": 20},
    {"name": "تلویزیون ۷۵ اینچ 4K", "sku": "TV-005", "price": 79000000, "stock": 0},
    {"name": "ساندبار ۲٫۱ کانال", "sku": "SND-001", "price": 6400000, "stock": 18},
    {"name": "سینمای خانگی ۵٫۱ کانال", "sku": "SND-002", "price": 14500000, "stock": 8},
    {"name": "اسپیکر بلوتوثی قابل‌حمل", "sku": "SND-003", "price": 2900000, "stock": 30},
    {"name": "پایه دیواری تلویزیون", "sku": "SND-004", "price": 850000, "stock": 45},
    {"name": "گیرنده دیجیتال", "sku": "SND-005", "price": 1600000, "stock": 40},
    # ── FRIDGE / FREEZER ──
    {"name": "یخچال فریزر ساید ۳۰ فوت", "sku": "FR-001", "price": 68000000, "stock": 5},
    {"name": "یخچال فریزر دوقلو", "sku": "FR-002", "price": 74000000, "stock": 4},
    {"name": "یخچال فریزر بالا پایین ۲۶ فوت", "sku": "FR-003", "price": 42000000, "stock": 8},
    {"name": "یخچال فریزر کمبی ۲۰ فوت", "sku": "FR-004", "price": 31500000, "stock": 10},
    {"name": "فریزر صندوقی ۲۵۰ لیتری", "sku": "FR-005", "price": 18700000, "stock": 9},
    {"name": "یخچال تک ۱۲ فوت", "sku": "FR-006", "price": 22300000, "stock": 11},
    {"name": "یخچال مینی‌بار هتلی", "sku": "FR-007", "price": 12900000, "stock": 14},
    {"name": "آبسردکن یخچال‌دار", "sku": "FR-008", "price": 9800000, "stock": 13},
    # ── WASH / DISH / CLEAN ──
    {"name": "ماشین لباسشویی ۹ کیلویی", "sku": "WASH-001", "price": 33000000, "stock": 9},
    {"name": "ماشین لباسشویی ۸ کیلویی", "sku": "WASH-002", "price": 27500000, "stock": 12},
    {
        "name": "ماشین لباسشویی خشک‌کن‌دار ۱۰٫۵ کیلویی",
        "sku": "WASH-003",
        "price": 46000000,
        "stock": 5,
    },
    {"name": "خشک‌کن ۸ کیلویی", "sku": "WASH-004", "price": 29800000, "stock": 6},
    {"name": "ماشین ظرفشویی ۱۴ نفره", "sku": "DISH-001", "price": 34500000, "stock": 8},
    {"name": "ماشین ظرفشویی ۱۳ نفره", "sku": "DISH-002", "price": 28900000, "stock": 10},
    {"name": "ماشین ظرفشویی رومیزی", "sku": "DISH-003", "price": 19400000, "stock": 7},
    {"name": "جاروبرقی کیسه‌ای ۲۰۰۰ وات", "sku": "VAC-001", "price": 8200000, "stock": 22},
    {"name": "جاروبرقی مخزن‌دار", "sku": "VAC-002", "price": 6700000, "stock": 25},
    {"name": "جاروشارژی عصایی", "sku": "VAC-003", "price": 11300000, "stock": 16},
    {"name": "ربات جاروبرقی", "sku": "VAC-004", "price": 21000000, "stock": 6},
    {"name": "بخارشوی چندکاره", "sku": "VAC-005", "price": 7600000, "stock": 15},
    {"name": "اتو بخار ایستاده", "sku": "IRON-001", "price": 5400000, "stock": 19},
    {"name": "اتو بخار دستی", "sku": "IRON-002", "price": 2300000, "stock": 35},
    # ── COOKING ──
    {"name": "اجاق‌گاز ۵ شعله فر‌دار", "sku": "GAS-001", "price": 21500000, "stock": 10},
    {"name": "اجاق‌گاز صفحه‌ای ۵ شعله", "sku": "GAS-002", "price": 13800000, "stock": 14},
    {"name": "اجاق‌گاز رومیزی ۲ شعله", "sku": "GAS-003", "price": 3900000, "stock": 28},
    {"name": "فر توکار برقی", "sku": "OVEN-001", "price": 24000000, "stock": 7},
    {"name": "فر توکار گازی", "sku": "OVEN-002", "price": 19700000, "stock": 8},
    {"name": "هود مورب آشپزخانه", "sku": "OVEN-003", "price": 8600000, "stock": 17},
    {"name": "هود زیرکابینتی", "sku": "OVEN-004", "price": 5100000, "stock": 21},
    {"name": "مایکروویو ۳۰ لیتری", "sku": "MW-001", "price": 9500000, "stock": 18},
    {"name": "مایکروویو ۲۵ لیتری", "sku": "MW-002", "price": 7200000, "stock": 23},
    {"name": "سرخ‌کن بدون روغن ۵٫۵ لیتری", "sku": "FRY-001", "price": 6800000, "stock": 26},
    {"name": "سرخ‌کن دوقلو ۹ لیتری", "sku": "FRY-002", "price": 11900000, "stock": 12},
    # ── COOLING / HEATING ──
    {"name": "کولر گازی ۲۴ هزار", "sku": "AC-001", "price": 42000000, "stock": 6},
    {"name": "کولر گازی ۱۸ هزار", "sku": "AC-002", "price": 35500000, "stock": 8},
    {"name": "کولر گازی ۱۲ هزار", "sku": "AC-003", "price": 29000000, "stock": 10},
    {"name": "کولر آبی ۷۰۰۰", "sku": "AC-004", "price": 13200000, "stock": 15},
    {"name": "پنکه ایستاده", "sku": "AC-005", "price": 2400000, "stock": 40},
    {"name": "بخاری گازی ۱۲ هزار", "sku": "HEAT-001", "price": 8900000, "stock": 16},
    {"name": "شوفاژ برقی ۱۳ پره", "sku": "HEAT-002", "price": 6300000, "stock": 20},
    {"name": "بخاری برقی فن‌دار", "sku": "HEAT-003", "price": 1800000, "stock": 50},
    {"name": "تصفیه هوای خانگی", "sku": "AIR-001", "price": 9700000, "stock": 11},
    {"name": "رطوبت‌ساز سرد", "sku": "AIR-002", "price": 3100000, "stock": 24},
    # ── FURNITURE ──
    {"name": "مبل راحتی ۷ نفره", "sku": "SOFA-001", "price": 38000000, "stock": 4},
    {"name": "مبل ال ۵ نفره", "sku": "SOFA-002", "price": 31000000, "stock": 5},
    {"name": "مبل تختخواب‌شو", "sku": "SOFA-003", "price": 17500000, "stock": 8},
    {"name": "صندلی راحتی تک‌نفره", "sku": "SOFA-004", "price": 6900000, "stock": 18},
    {"name": "میز جلو‌مبلی چوبی", "sku": "TABLE-001", "price": 4800000, "stock": 22},
    {"name": "میز ناهارخوری ۶ نفره", "sku": "TABLE-002", "price": 16200000, "stock": 6},
    {"name": "میز تلویزیون", "sku": "TABLE-003", "price": 5600000, "stock": 19},
    {"name": "کتابخانه چوبی", "sku": "TABLE-004", "price": 7300000, "stock": 13},
    {"name": "سرویس خواب دونفره", "sku": "BED-001", "price": 29000000, "stock": 5},
    {"name": "تخت یک‌نفره", "sku": "BED-002", "price": 11400000, "stock": 9},
    {"name": "تشک دونفره طبی", "sku": "BED-003", "price": 13800000, "stock": 12},
    {"name": "کمد لباس ۳ درب", "sku": "BED-004", "price": 14600000, "stock": 7},
    # ── SMALL KITCHEN APPLIANCES ──
    {"name": "غذاساز چندکاره", "sku": "FOOD-001", "price": 7900000, "stock": 17},
    {"name": "پلوپز چندکاره", "sku": "FOOD-002", "price": 4700000, "stock": 25},
    {"name": "آرام‌پز", "sku": "FOOD-003", "price": 2800000, "stock": 30},
    {"name": "چرخ‌گوشت ۲۰۰۰ وات", "sku": "MEAT-001", "price": 6100000, "stock": 20},
    {"name": "آبمیوه‌گیری ۴ کاره", "sku": "JUICE-001", "price": 5200000, "stock": 23},
    {"name": "چای‌ساز سماوری", "sku": "KETTLE-001", "price": 4300000, "stock": 27},
    {"name": "کتری برقی", "sku": "KETTLE-002", "price": 1900000, "stock": 55},
    {"name": "قهوه‌ساز اسپرسو", "sku": "COFFEE-001", "price": 12500000, "stock": 10},
    {"name": "قهوه‌ساز فرانسه", "sku": "COFFEE-002", "price": 3400000, "stock": 21},
    {"name": "توستر نان", "sku": "TOAST-001", "price": 2200000, "stock": 33},
    {"name": "مخلوط‌کن و آسیاب", "sku": "MIX-001", "price": 3100000, "stock": 29},
    {"name": "همزن برقی", "sku": "MIX-002", "price": 2600000, "stock": 31},
    # ── LIGHTING ──
    {"name": "لوستر ۶ شاخه", "sku": "LUST-001", "price": 9800000, "stock": 9},
    {"name": "لوستر مدرن LED", "sku": "LUST-002", "price": 12300000, "stock": 7},
    {"name": "آباژور ایستاده", "sku": "LAMP-001", "price": 3600000, "stock": 16},
    {"name": "آباژور رومیزی", "sku": "LAMP-002", "price": 1700000, "stock": 28},
    {"name": "چراغ خواب", "sku": "LAMP-003", "price": 950000, "stock": 42},
    {"name": "پنل LED سقفی", "sku": "LAMP-004", "price": 1200000, "stock": 60},
]


def main() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    added = 0
    removed = 0
    with Session(engine) as session:
        cat_ids: dict[str, int] = {}
        for name in CATEGORIES:
            cat = session.scalar(select(Category).where(Category.name == name))
            if cat is None:
                cat = Category(name=name)
                session.add(cat)
                session.flush()
            cat_ids[name] = cat.id
        new_skus = {str(item["sku"]) for item in PRODUCTS}
        for item in PRODUCTS:
            sku = str(item["sku"])
            prefix = sku.split("-")[0] if "-" in sku else sku
            category_id = cat_ids.get(PREFIX_CATEGORY.get(prefix, "لوازم برقی آشپزخانه"), None)
            existing = session.scalar(select(Product).where(Product.sku == item["sku"]))
            if existing is not None:
                # Re-run syncs seed values (e.g. stock changes), not just new rows.
                existing.name = str(item["name"])
                existing.price = int(item["price"])  # type: ignore[arg-type]
                existing.stock = int(item["stock"])  # type: ignore[arg-type]
                existing.category_id = category_id
                continue
            session.add(
                Product(
                    **item,  # type: ignore[arg-type]
                    category_id=category_id,
                )
            )
            added += 1
        # Re-run replaces old catalog: products absent from PRODUCTS are removed.
        for stale in session.scalars(select(Product).where(Product.sku.not_in(new_skus))).all():
            session.delete(stale)
            removed += 1
        session.flush()
        for cat in session.scalars(select(Category)).all():
            if cat.name in CATEGORIES:
                continue
            has_products = (
                session.scalar(select(Product.id).where(Product.category_id == cat.id)) is not None
            )
            if not has_products:
                session.delete(cat)
        session.commit()
    total = len(PRODUCTS)
    print(f"{added} new products added ({total - added} already existed), {removed} stale removed")


if __name__ == "__main__":
    main()
