"""Development catalog source — Parsina-shaped rows from a local CSV fixture.

The file is an export of the live catalog (same field names as `GET /Commodity`),
so it flows through the exact same validation and sync path as the API rows.
Headers and values carry padding whitespace in the export, hence the stripping.

Production resolves `countUnit` titles through `GET /UnitCount/BaseInfo`; the
export only carries the ids, so this source mirrors that endpoint with the mock
titles below — the dev catalog must look exactly like a production one.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Literal

# Mock titles for the unit ids present in the dev export. Replace them if the
# real `/UnitCount/BaseInfo` titles differ; unknown ids fall back to "عدد".
_DEV_UNIT_TITLES: dict[int, str] = {
    1: "تخته",
    2: "ست",
    3: "دستگاه",
    4: "عدد",
    5: "متر",
}
_DEV_UNIT_FALLBACK = "عدد"


class CsvSourceError(Exception):
    """The development fixture is missing, unreadable, or malformed."""


def _normalise(raw: dict[str, str | None]) -> dict[str, Any]:
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


class CsvCommoditySource:
    """Read the dev catalog file on demand; no network, no credentials."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()

    @property
    def label(self) -> Literal["csv"]:
        return "csv"

    @property
    def path(self) -> Path:
        return self._path

    @property
    def is_configured(self) -> bool:
        return self._path.is_file()

    def fetch(self) -> tuple[list[dict[str, Any]], int | None, dict[int, str]]:
        """Raw rows + reported total + unit titles (mocked, see module docstring)."""
        try:
            with self._path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = [_normalise(raw) for raw in reader]
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise CsvSourceError(f"فایل {self._path.name} خوانده نشد") from exc
        return rows, len(rows), _unit_titles(rows)
