"""Saved cardex source — Parsina-shaped invoice envelopes from a fixture dir.

Mirrors the live `GET /SaleFactor`, `/buyFactor`, and their `/{id}` detail
endpoints exactly (same envelope, same field names), so Development and the
Staging simulation show the same cardex shape as production without
credentials or network access.

The saved dumps are paired by id: `sale-factors.json` holds invoice headers,
`sale-factor-details.json` holds the corresponding `Details[]` records.
Development reads `data/`; Staging reads the fixtures bundled with the API
(see `Settings.resolved_fixture_dir`).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from app.core.config import get_settings
from app.integrations.parsina import field, integer

CARDEX_FIXTURES = (
    "sale-factors.json",
    "buy-factors.json",
    "sale-factor-details.json",
    "buy-factor-details.json",
)


class CardexFixtureError(Exception):
    """A saved cardex response is missing, unreadable, or malformed."""


def _envelope(path: Path) -> list[dict[str, Any]]:
    try:
        body = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CardexFixtureError(f"فایل {path.name} خوانده نشد") from exc
    envelope = cast("dict[str, Any]", body) if isinstance(body, dict) else None
    if envelope is None or envelope.get("isSuccess") is False:
        raise CardexFixtureError(f"فایل {path.name} معتبر نیست")
    rows: Any = envelope.get("data")
    if not isinstance(rows, list):
        raise CardexFixtureError(f"فایل {path.name} فاقد لیست data است")
    typed_rows = cast("list[Any]", rows)
    return [cast("dict[str, Any]", row) for row in typed_rows if isinstance(row, dict)]


def _jalali(date_value: date) -> str:
    # Pure-Python Jalali conversion (the backend's single source is jdatetime;
    # this fixture reader only needs the key used by the saved dump).
    import jdatetime  # type: ignore[import-untyped]

    jalali = jdatetime.date.fromgregorian(date=date_value)  # type: ignore[reportUnknownMemberType]
    return f"{jalali.year}/{jalali.month:02d}/{jalali.day:02d}"


class CardexFixtureSource:
    """Filter the saved Parsina invoices by the same Jalali window as live."""

    def __init__(self, *, directory: Path | None = None) -> None:
        base = directory or Path(get_settings().products_csv_path).parent
        self._directory = Path(base).expanduser()

    @property
    def is_configured(self) -> bool:
        return all((self._directory / name).is_file() for name in CARDEX_FIXTURES)

    def invoices(self, *, kind: str, from_date: date, to_date: date) -> list[dict[str, Any]]:
        name = "sale-factors.json" if kind == "sale" else "buy-factors.json"
        path = self._directory / name
        if not path.is_file():
            return []
        start, end = _jalali(from_date), _jalali(to_date)
        rows = [row for row in _envelope(path) if start <= str(field(row, "Date") or "") <= end]
        return rows

    def details(self, *, kind: str, invoice_id: int) -> list[dict[str, Any]]:
        name = "sale-factor-details.json" if kind == "sale" else "buy-factor-details.json"
        path = self._directory / name
        if not path.is_file():
            return []
        for row in _envelope(path):
            if integer(field(row, "id")) == invoice_id:
                details = field(row, "Details")
                if isinstance(details, list):
                    typed_details = cast("list[Any]", details)
                    return [
                        cast("dict[str, Any]", line)
                        for line in typed_details
                        if isinstance(line, dict)
                    ]
                return []
        return []
