"""Catalog sections (تقسیم‌بندی) — one classification rule for the whole app.

Parsina `mainGroupName` values are grouped into the sections shown by the
products table, list filters, dashboard, and CSV exports:

- فرش / مبلمان — the two tracking-only sections (daily price change).
- لوازم خانگی — every remaining group that is not digital.
- کالای دیجیتال — consoles, phones/tablets, and laptops/PCs.

Digital groups are matched by their name prefix. Parsina reuses/renumbers
`mainGroup` ids between catalog exports (id 7 was a laptop group in the old CSV
but is «لوازم خانگی بلانتون» in the new one), so an id alone must never override
a group name. The id set is only a fallback for rows with no name at all, like
older manual rows.
"""

import re
from typing import Literal

TopGroup = Literal["کالای دیجیتال", "لوازم خانگی", "فرش", "مبلمان"]

TOP_GROUPS: tuple[TopGroup, ...] = ("کالای دیجیتال", "لوازم خانگی", "فرش", "مبلمان")

# Ids of the digital groups in the current Parsina catalog; used only when a
# row has no group name. Names are authoritative — see module docstring.
DIGITAL_MAIN_GROUP_IDS: frozenset[int] = frozenset({27, 28, 29})
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
    """True when the row belongs to the digital section.

    A group name wins over the id; ids drift between Parsina exports, so an old
    digital id on an appliance group must not misclassify it (and drag it to
    the top of the category sort).
    """
    text = (name or "").strip()
    if text:
        return text.startswith(DIGITAL_MAIN_GROUP_PREFIXES)
    return main_group_id in DIGITAL_MAIN_GROUP_IDS if main_group_id is not None else False


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
