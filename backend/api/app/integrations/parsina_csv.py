"""Development catalog source — Parsina-shaped rows from a local fixture.

The file mirrors the live catalog (same field names as `GET /Commodity`), so it
flows through the exact same validation and sync path as the API rows. Two
shapes are accepted:

- `products.json` — the saved Parsina response envelope, preferred when it sits
  next to the fixture. It carries real count-unit titles via `units.json`.
- `parsina.csv` — the older export (headers/values carry padding, hence the
  stripping below). It only has unit ids, so the mock titles below stand in for
  the live counting-units endpoint; the dev catalog must look like a production one.

`build_commodity_source`, the scheduler, and `make db-seed-parsina` all go
through this one class, so the «بهروزرسانی از پارسینا» button, the automatic
sync, and the seed script read the same rows.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Literal

from app.integrations.parsina import unit_titles_from_rows

# Titles for the unit ids of the older CSV export, from the counting-units
# endpoint in `data/units.json` (the same Id/Title map the live sync uses).
# `units.json` is always preferred when present; this table is only a fallback
# for a bare CSV export with no saved units response beside it.
_DEV_UNIT_TITLES: dict[int, str] = {
    1: "لنگه",
    2: "عدل",
    3: "جعبه",
    4: "توپ",
    5: "ست",
}
_DEV_UNIT_FALLBACK = "عدد"


class CsvSourceError(Exception):
    """The development fixture is missing, unreadable, or malformed."""


def _normalise(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        (key or "").strip(): value.strip() if isinstance(value, str) else value
        for key, value in raw.items()
    }


def _unit_id(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _unit_titles(rows: list[dict[str, Any]]) -> dict[int, str]:
    """Give every referenced unit a title so dev mirrors the production output."""
    titles: dict[int, str] = {}
    for row in rows:
        unit_id = _unit_id(row.get("countUnit"))
        if unit_id is not None:
            titles[unit_id] = _DEV_UNIT_TITLES.get(unit_id, _DEV_UNIT_FALLBACK)
    return titles


def _json_envelope(path: Path) -> dict[str, Any]:
    """Read one saved Parsina response (catalog or counting units)."""
    try:
        body = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CsvSourceError(f"فایل {path.name} خوانده نشد") from exc
    if not isinstance(body, dict) or body.get("isSuccess") is False:
        raise CsvSourceError(f"فایل {path.name} معتبر نیست")
    data = body.get("data")
    if not isinstance(data, list):
        raise CsvSourceError(f"فایل {path.name} فاقد لیست data است")
    return {"total": body.get("total"), "rows": data}


def _json_unit_titles(units_path: Path, fallback: dict[int, str]) -> dict[int, str]:
    """Prefer real titles from `units.json`; mock only the units it omits."""
    titles = dict(fallback)
    if not units_path.is_file():
        return titles
    envelope = _json_envelope(units_path)
    # Exactly the same Id/Title mapping the live Parsina client uses.
    titles.update(unit_titles_from_rows(envelope["rows"]))
    return titles


class CsvCommoditySource:
    """Read the dev catalog fixture on demand; no network, no credentials."""

    def __init__(self, path: str | Path) -> None:
        path = Path(path).expanduser()
        # The saved products.json dump is the same source production uses; use
        # it whenever it is available next to the configured CSV path.
        if path.suffix.lower() == ".csv":
            dump = path.with_name("products.json")
            if dump.is_file():
                path = dump
        self._path = path

    @property
    def label(self) -> Literal["csv"]:
        # The API contract exposes parsina/csv/dev; the JSON dump is the dev
        # fixture in its newer shape, so it keeps the same source label.
        return "csv"

    @property
    def path(self) -> Path:
        return self._path

    @property
    def is_configured(self) -> bool:
        return self._path.is_file()

    @property
    def is_full_catalog(self) -> bool:
        # The dev fixture is the complete development mirror.
        return True

    def fetch(self) -> tuple[list[dict[str, Any]], int | None, dict[int, str]]:
        """Raw rows + reported total + unit titles (see module docstring)."""
        if self._path.suffix.lower() == ".json":
            envelope = _json_envelope(self._path)
            rows = [_normalise(raw) for raw in envelope["rows"] if isinstance(raw, dict)]
            total = _unit_id(envelope["total"])
            units = _json_unit_titles(self._path.with_name("units.json"), _unit_titles(rows))
            return rows, total, units
        try:
            with self._path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = [_normalise(raw) for raw in reader]
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise CsvSourceError(f"فایل {self._path.name} خوانده نشد") from exc
        # The saved units export is authoritative for CSV rows too; only mock
        # the ids it does not cover so dev never shows a wrong unit title.
        titles = _json_unit_titles(self._path.with_name("units.json"), _unit_titles(rows))
        return rows, len(rows), titles
