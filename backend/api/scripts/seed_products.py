"""Seed demo products — idempotent, safe to re-run.

Machine-readable values only (integer toman, plain SKUs).
Persian display formatting happens in the UI.
Run via `make seed-products` from the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base, get_engine
from app.models import Category, Product

CATEGORIES: list[str] = ["خواربار", "لبنیات", "ادویه", "شیرینی"]

# ponytail: prefix map covers current seed SKUs; new prefixes fall back to خواربار.
PREFIX_CATEGORY: dict[str, str] = {
    "TEA": "خواربار",
    "COF": "خواربار",
    "RICE": "خواربار",
    "FLOUR": "خواربار",
    "OAT": "خواربار",
    "PASTA": "خواربار",
    "LENT": "خواربار",
    "PEA": "خواربار",
    "BEAN": "خواربار",
    "BEANC": "خواربار",
    "OIL": "خواربار",
    "SES": "خواربار",
    "HONEY": "خواربار",
    "JAM": "خواربار",
    "HV": "خواربار",
    "SAFFRON": "ادویه",
    "SPI": "ادویه",
    "PISTA": "خواربار",
    "ALM": "خواربار",
    "HAZ": "خواربار",
    "WALNUT": "خواربار",
    "CASH": "خواربار",
    "SUN": "خواربار",
    "PUM": "خواربار",
    "RAISIN": "خواربار",
    "FIG": "خواربار",
    "MUL": "خواربار",
    "APR": "خواربار",
    "DATE": "خواربار",
    "PRU": "خواربار",
    "CHIPF": "خواربار",
    "LIGH": "لبنیات",
    "CHE": "لبنیات",
    "YOG": "لبنیات",
    "KASHK": "لبنیات",
    "DOUGH": "لبنیات",
    "BUT": "لبنیات",
    "CREAM": "لبنیات",
    "PASTE": "خواربار",
    "TUN": "خواربار",
    "CORN": "خواربار",
    "PICK": "خواربار",
    "OLIVE": "خواربار",
    "NABAT": "شیرینی",
    "SOHAN": "شیرینی",
    "GAZ": "شیرینی",
    "PUL": "شیرینی",
    "BAGH": "شیرینی",
    "KOL": "شیرینی",
    "BAS": "شیرینی",
    "LAV": "شیرینی",
    "CHIPS": "خواربار",
    "SNACK": "خواربار",
    "ARAQ": "خواربار",
    "SHAR": "خواربار",
    "LIME": "خواربار",
    "SALT": "ادویه",
    "SUG": "شیرینی",
}

PRODUCTS: list[dict[str, str | int]] = [
    # ── TEA / COFFEE ──
    {"name": "چای ایرانی بهاره", "sku": "TEA-001", "price": 450000, "stock": 24},
    {"name": "چای دارجیلینگ ممتاز", "sku": "TEA-002", "price": 680000, "stock": 18},
    {"name": "چای سبز گن‌پاودر", "sku": "TEA-003", "price": 390000, "stock": 30},
    {"name": "دمنوش بابونه", "sku": "TEA-004", "price": 180000, "stock": 45},
    {"name": "دمنوش گل‌گاوزبان", "sku": "TEA-005", "price": 220000, "stock": 40},
    {"name": "قهوه عربیکا تازه‌برشت", "sku": "COF-001", "price": 1450000, "stock": 16},
    {"name": "قهوه روبوستا اسپرسو", "sku": "COF-002", "price": 1180000, "stock": 20},
    {"name": "پودر قهوه فوری گلد", "sku": "COF-003", "price": 560000, "stock": 35},
    {"name": "پودر قهوه فوری کلاسیک", "sku": "COF-004", "price": 420000, "stock": 28},
    {"name": "کاپوچینو فوری", "sku": "COF-005", "price": 310000, "stock": 33},
    # ── RICE / GRAINS ──
    {"name": "برنج طارم هاشمی", "sku": "RICE-001", "price": 1850000, "stock": 40},
    {"name": "برنج دم‌سیاه آستانه", "sku": "RICE-002", "price": 2100000, "stock": 25},
    {"name": "برنج نیم‌دانه", "sku": "RICE-003", "price": 950000, "stock": 60},
    {"name": "برنج قهوه‌ای", "sku": "RICE-004", "price": 780000, "stock": 22},
    {"name": "آرد گندم کامل", "sku": "FLOUR-001", "price": 150000, "stock": 70},
    {"name": "آرد برنج", "sku": "FLOUR-002", "price": 190000, "stock": 55},
    {"name": "آرد نخودچی", "sku": "FLOUR-003", "price": 260000, "stock": 48},
    {"name": "جو پرک", "sku": "OAT-001", "price": 170000, "stock": 52},
    {"name": "بلغور گندم", "sku": "OAT-002", "price": 140000, "stock": 44},
    {"name": "ماکارونی رشته‌ای", "sku": "PASTA-001", "price": 95000, "stock": 120},
    {"name": "ماکارونی فرمی", "sku": "PASTA-002", "price": 98000, "stock": 110},
    {"name": "رشته آش", "sku": "PASTA-003", "price": 110000, "stock": 90},
    {"name": "رشته سوپ", "sku": "PASTA-004", "price": 88000, "stock": 95},
    # ── LEGUMES ──
    {"name": "عدس قرمز", "sku": "LENT-001", "price": 240000, "stock": 65},
    {"name": "عدس سبز", "sku": "LENT-002", "price": 230000, "stock": 58},
    {"name": "نخود آبگوشتی", "sku": "PEA-001", "price": 310000, "stock": 50},
    {"name": "لپه آذرشهر", "sku": "PEA-002", "price": 360000, "stock": 38},
    {"name": "لوبیا چیتی", "sku": "BEAN-001", "price": 340000, "stock": 47},
    {"name": "لوبیا قرمز", "sku": "BEAN-002", "price": 330000, "stock": 42},
    {"name": "لوبیا سفید", "sku": "BEAN-003", "price": 320000, "stock": 40},
    {"name": "لوبیا چشم‌بلبلی", "sku": "BEAN-004", "price": 350000, "stock": 36},
    {"name": "ماش سبز", "sku": "BEAN-005", "price": 290000, "stock": 44},
    # ── OILS ──
    {"name": "روغن کنجد پرس سرد", "sku": "OIL-001", "price": 890000, "stock": 15},
    {"name": "روغن زیتون فرابکر", "sku": "OIL-002", "price": 1650000, "stock": 14},
    {"name": "روغن آفتابگردان", "sku": "OIL-003", "price": 420000, "stock": 80},
    {"name": "روغن حیوانی کرمانشاهی", "sku": "OIL-004", "price": 1980000, "stock": 10},
    {"name": "روغن کنجد معمولی", "sku": "OIL-005", "price": 640000, "stock": 26},
    {"name": "ارده کنجد", "sku": "SES-001", "price": 480000, "stock": 32},
    {"name": "کره بادام‌زمینی طبیعی", "sku": "SES-002", "price": 590000, "stock": 21},
    # ── HONEY / JAM / BREAKFAST ──
    {"name": "عسل طبیعی سبلان", "sku": "HONEY-001", "price": 1250000, "stock": 12},
    {"name": "عسل کنار", "sku": "HONEY-002", "price": 1890000, "stock": 9},
    {"name": "عسل گون", "sku": "HONEY-003", "price": 1420000, "stock": 11},
    {"name": "مربای آلبالو", "sku": "JAM-001", "price": 280000, "stock": 34},
    {"name": "مربای به", "sku": "JAM-002", "price": 260000, "stock": 29},
    {"name": "مربای هویج", "sku": "JAM-003", "price": 220000, "stock": 37},
    {"name": "شیره انگور", "sku": "JAM-004", "price": 390000, "stock": 23},
    {"name": "شیره خرما", "sku": "JAM-005", "price": 340000, "stock": 27},
    {"name": "حلوا شکری", "sku": "HV-001", "price": 310000, "stock": 31},
    {"name": "حلوا ارده", "sku": "HV-002", "price": 360000, "stock": 24},
    # ── SPICES ──
    {"name": "زعفران قائنات نیم‌مثقال", "sku": "SAFFRON-001", "price": 9800000, "stock": 8},
    {"name": "زعفران قائنات یک‌مثقال", "sku": "SAFFRON-002", "price": 17500000, "stock": 5},
    {"name": "زردچوبه قلم", "sku": "SPI-001", "price": 180000, "stock": 66},
    {"name": "فلفل سیاه آسیاب‌شده", "sku": "SPI-002", "price": 450000, "stock": 33},
    {"name": "فلفل قرمز", "sku": "SPI-003", "price": 290000, "stock": 41},
    {"name": "دارچین قلم", "sku": "SPI-004", "price": 520000, "stock": 27},
    {"name": "هل سبز", "sku": "SPI-005", "price": 2900000, "stock": 7},
    {"name": "زیره سبز", "sku": "SPI-006", "price": 610000, "stock": 25},
    {"name": "سماق قرمز", "sku": "SPI-007", "price": 380000, "stock": 30},
    {"name": "آویشن شیرازی", "sku": "SPI-008", "price": 150000, "stock": 58},
    {"name": "نعناع خشک", "sku": "SPI-009", "price": 130000, "stock": 62},
    {"name": "پودر سیر", "sku": "SPI-010", "price": 240000, "stock": 39},
    {"name": "زنجبیل آسیاب‌شده", "sku": "SPI-011", "price": 330000, "stock": 28},
    {"name": "گلپر", "sku": "SPI-012", "price": 270000, "stock": 35},
    # ── NUTS / DRIED ──
    {"name": "پسته اکبری شور", "sku": "PISTA-001", "price": 2300000, "stock": 20},
    {"name": "پسته احمدآقایی", "sku": "PISTA-002", "price": 1950000, "stock": 22},
    {"name": "بادام درختی", "sku": "ALM-001", "price": 1680000, "stock": 19},
    {"name": "بادام‌زمینی", "sku": "ALM-002", "price": 720000, "stock": 43},
    {"name": "فندق خام", "sku": "HAZ-001", "price": 1890000, "stock": 13},
    {"name": "گردوی پوست‌کاغذی", "sku": "WALNUT-001", "price": 1750000, "stock": 18},
    {"name": "بادام هندی", "sku": "CASH-001", "price": 2450000, "stock": 12},
    {"name": "تخمه آفتابگردان", "sku": "SUN-001", "price": 280000, "stock": 75},
    {"name": "تخمه کدو", "sku": "PUM-001", "price": 420000, "stock": 46},
    {"name": "کشمش پلویی آفتابی", "sku": "RAISIN-001", "price": 340000, "stock": 35},
    {"name": "مویز بی‌دانه", "sku": "RAISIN-002", "price": 460000, "stock": 29},
    {"name": "انجیر خشک", "sku": "FIG-001", "price": 890000, "stock": 17},
    {"name": "توت خشک", "sku": "MUL-001", "price": 640000, "stock": 26},
    {"name": "برگه زردآلو", "sku": "APR-001", "price": 780000, "stock": 20},
    {"name": "خرمای مضافتی بم", "sku": "DATE-001", "price": 380000, "stock": 50},
    {"name": "خرمای پیارم", "sku": "DATE-002", "price": 1450000, "stock": 15},
    {"name": "خرمای زاهدی", "sku": "DATE-003", "price": 260000, "stock": 68},
    {"name": "آلو بخارا", "sku": "PRU-001", "price": 580000, "stock": 24},
    {"name": "چیپس میوه مخلوط", "sku": "CHIPF-001", "price": 490000, "stock": 22},
    # ── DAIRY ──
    {"name": "پنیر لیقوان", "sku": "LIGH-001", "price": 780000, "stock": 16},
    {"name": "پنیر سفید تبریزی", "sku": "CHE-001", "price": 540000, "stock": 28},
    {"name": "ماست چکیده", "sku": "YOG-001", "price": 190000, "stock": 40},
    {"name": "کشک خشک", "sku": "KASHK-001", "price": 420000, "stock": 33},
    {"name": "دوغ گازدار", "sku": "DOUGH-001", "price": 85000, "stock": 150},
    {"name": "کره محلی", "sku": "BUT-001", "price": 880000, "stock": 18},
    {"name": "خامه عسلی", "sku": "CREAM-001", "price": 240000, "stock": 25},
    # ── CANNED / PASTE / PICKLES ──
    {"name": "رب گوجه خانگی", "sku": "PASTE-001", "price": 290000, "stock": 30},
    {"name": "رب انار", "sku": "PASTE-002", "price": 690000, "stock": 19},
    {"name": "کنسرو ماهی تن", "sku": "TUN-001", "price": 320000, "stock": 85},
    {"name": "کنسرو لوبیا", "sku": "BEANC-001", "price": 150000, "stock": 95},
    {"name": "کنسرو ذرت", "sku": "CORN-001", "price": 170000, "stock": 88},
    {"name": "خیارشور ویژه", "sku": "PICK-001", "price": 230000, "stock": 54},
    {"name": "ترشی مخلوط", "sku": "PICK-002", "price": 250000, "stock": 47},
    {"name": "زیتون شور", "sku": "OLIVE-001", "price": 480000, "stock": 31},
    # ── SNACKS / SWEETS ──
    {"name": "نبات شاخه‌ای زعفرانی", "sku": "NABAT-001", "price": 210000, "stock": 60},
    {"name": "نبات چوبی", "sku": "NABAT-002", "price": 240000, "stock": 55},
    {"name": "سوهان عسلی قم", "sku": "SOHAN-001", "price": 520000, "stock": 25},
    {"name": "گز آردی اصفهان", "sku": "GAZ-001", "price": 920000, "stock": 14},
    {"name": "پولکی نعنایی", "sku": "PUL-001", "price": 180000, "stock": 72},
    {"name": "باقلوا استانبولی", "sku": "BAGH-001", "price": 1250000, "stock": 10},
    {"name": "کلوچه فومن", "sku": "KOL-001", "price": 160000, "stock": 83},
    {"name": "باسلوق", "sku": "BAS-001", "price": 380000, "stock": 26},
    {"name": "لواشک آلبالو", "sku": "LAV-001", "price": 190000, "stock": 64},
    {"name": "لواشک مخلوط", "sku": "LAV-002", "price": 175000, "stock": 61},
    {"name": "چیپس خلالی", "sku": "CHIPS-001", "price": 140000, "stock": 110},
    {"name": "ذرت حجیم‌شده", "sku": "SNACK-001", "price": 95000, "stock": 130},
    # ── DRINKS / SYRUPS ──
    {"name": "عرق نعناع", "sku": "ARAQ-001", "price": 150000, "stock": 57},
    {"name": "عرق بیدمشک", "sku": "ARAQ-002", "price": 165000, "stock": 49},
    {"name": "گلاب قمصر", "sku": "ARAQ-003", "price": 210000, "stock": 45},
    {"name": "شربت سکنجبین", "sku": "SHAR-001", "price": 230000, "stock": 38},
    {"name": "آب‌لیمو طبیعی", "sku": "LIME-001", "price": 290000, "stock": 36},
    # ── PANTRY ──
    {"name": "نمک دریا", "sku": "SALT-001", "price": 60000, "stock": 200},
    {"name": "نمک صورتی", "sku": "SALT-002", "price": 140000, "stock": 90},
    {"name": "شکر قهوه‌ای", "sku": "SUG-001", "price": 170000, "stock": 85},
    {"name": "قند شکسته", "sku": "SUG-002", "price": 150000, "stock": 95},
]


def main() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    added = 0
    with Session(engine) as session:
        cat_ids: dict[str, int] = {}
        for name in CATEGORIES:
            cat = session.scalar(select(Category).where(Category.name == name))
            if cat is None:
                cat = Category(name=name)
                session.add(cat)
                session.flush()
            cat_ids[name] = cat.id
        for item in PRODUCTS:
            exists = session.scalar(select(Product.id).where(Product.sku == item["sku"]))
            if exists is not None:
                continue
            sku = str(item["sku"])
            prefix = sku.split("-")[0] if "-" in sku else sku
            session.add(
                Product(
                    **item,  # type: ignore[arg-type]
                    category_id=cat_ids.get(PREFIX_CATEGORY.get(prefix, "خواربار"), None),
                )
            )
            added += 1
        session.commit()
    total = len(PRODUCTS)
    print(f"{added} new products added ({total - added} already existed)")


if __name__ == "__main__":
    main()
