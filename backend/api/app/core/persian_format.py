"""Persian display formatting for CSV exports.

Machine values stay canonical in the database and the JSON API. Exports are
end-user files, so they carry Persian digits and Jalali dates — the same rules
the UI applies at render time (AGENTS.md §6). Never persist these strings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import jdatetime

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
# U+066B ARABIC DECIMAL SEPARATOR — the only allowed Jalali date separator.
DATE_SEP = "٫"
# Matches the UI's DECIMAL_SEP; thousands grouping is never applied in exports.
DECIMAL_SEP = "٫"
TEHRAN = ZoneInfo("Asia/Tehran")


def to_persian_digits(value: str) -> str:
    return value.translate(PERSIAN_DIGITS)


def format_amount(value: Decimal | float | int | None) -> str:
    """Persian digits, no thousands separator so Excel keeps the cell numeric.

    Trailing decimal zeros are dropped (1000000.00 → ۱۰۰۰۰۰۰).
    """
    if value is None:
        return ""
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return ""
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    text = text.replace(".", DECIMAL_SEP)
    return to_persian_digits(text)


def format_percent(value: Decimal | float | int | None) -> str:
    """Signed percent like the UI (`+۲٫۵٪`, `−۵٪`), empty for no value."""
    if value is None:
        return ""
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return ""
    sign = "+" if number > 0 else ("−" if number < 0 else "")
    text = format_amount(abs(number))
    return f"{sign}{text}٪" if text else ""


def format_jalali_datetime(value: datetime | None) -> str:
    """DB value in, `۱۴۰۵٫۰۸٫۲۱ ۱۶:۰۰` in Tehran time out.

    SQLite drops tzinfo, so naive values are treated as UTC like the rest of
    the backend (see `_aware` in the competitor service).
    """
    if value is None:
        return ""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    local = aware.astimezone(TEHRAN).replace(tzinfo=None)
    jalali = jdatetime.datetime.fromgregorian(datetime=local)
    return to_persian_digits(
        f"{jalali.year}{DATE_SEP}{jalali.month:02d}{DATE_SEP}{jalali.day:02d} "
        f"{jalali.hour:02d}:{jalali.minute:02d}"
    )


def format_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return "بله" if value else "خیر"
