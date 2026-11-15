"""Catalog sections (تقسیم‌بندی) — one classification rule for the whole app.

Parsina `mainGroupName` values are grouped into the sections shown by the
products table, list filters, dashboard, and CSV exports:

- فرش / مبلمان — the two tracking-only sections (daily price change).
- لوازم خانگی — every remaining group that is not digital.
- کالای دیجیتال — consoles, phones/tablets, and laptops/PCs.

Digital groups are matched by Parsina's `mainGroup` id and by a name prefix:
synced rows always carry the id, while manual/older rows may only have a name.
"""

import re
from typing import Literal

TopGroup = Literal["فرش", "مبلمان", "لوازم خانگی", "کالای دیجیتال"]

TOP_GROUPS: tuple[TopGroup, ...] = ("فرش", "مبلمان", "لوازم خانگی", "کالای دیجیتال")

# Parsina main groups that belong to کالای دیجیتال.
DIGITAL_MAIN_GROUP_IDS: frozenset[int] = frozenset({7, 56, 57})
DIGITAL_MAIN_GROUP_PREFIXES: tuple[str, ...] = (
    "کنسول بازی",
    "گوشی و تبلت",
    "لبت تاب",  # Parsina's spelling; «لپ تاپ» is the common one.
    "لپ تاپ",
)

CARPET_PREFIX = "فرش"
FURNITURE_PREFIX = "مبلمان"
APPLIANCE_PREFIX = "لوازم خانگی"
DIGITAL_GROUP = "کالای دیجیتال"


def is_digital_group(name: str | None, main_group_id: int | None = None) -> bool:
    """True when the row belongs to the digital section."""
    if main_group_id is not None and main_group_id in DIGITAL_MAIN_GROUP_IDS:
        return True
    text = (name or "").strip()
    return text.startswith(DIGITAL_MAIN_GROUP_PREFIXES)


def top_group_of(name: str | None, main_group_id: int | None = None) -> TopGroup | None:
    """Section (بخش) of one raw Parsina group; `None` when it has no group."""
    if is_digital_group(name, main_group_id):
        return "کالای دیجیتال"
    text = (name or "").strip()
    if not text:
        return None
    if text.startswith(CARPET_PREFIX):
        return "فرش"
    if text.startswith(FURNITURE_PREFIX):
        return "مبلمان"
    return "لوازم خانگی"


def compares_with_competitor(top: str | None) -> bool:
    """True when a fresh Digikala/Technolife price is a direct competitor price.

    Carpet and furniture instead link a daily price tracker (DigiFresh/Sofa).
    """
    return top in ("لوازم خانگی", "کالای دیجیتال")


def brand_of(name: str | None, top: str | None) -> str | None:
    """Display brand — the remainder after the section prefix.

    Digital groups have no brand prefix of their own, so the group name itself
    is the brand (e.g. «کنسول بازی»).
    """
    if not name:
        return None
    text = name.strip()
    if not text:
        return None
    if top == "فرش":
        rest = text.removeprefix(CARPET_PREFIX).strip()
        return rest or None
    if top == "مبلمان":
        rest = text.removeprefix(FURNITURE_PREFIX).strip()
        return rest or None
    if top == APPLIANCE_PREFIX:
        # Parsina uses both «خانگی» and the typo «خانکی».
        rest = re.sub(r"^لوازم\s+خان[گک]ی\s*", "", text).strip()
        return rest or text
    return text
