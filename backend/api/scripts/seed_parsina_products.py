"""Load the Parsina CSV export into the development database.

Development only. Replaces the whole product mirror with the CSV catalog so the
dev UI shows the same shaped data as production without Parsina credentials.
Run via `make db-seed-parsina` (which applies migrations first).

The CSV path defaults to `<repo>/data/parsina-products.csv` and can be
overridden with `PRODUCTS_CSV_PATH`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.integrations.parsina_csv import CsvCommoditySource
from app.services.sync import ProductSyncService


def main() -> int:
    settings = get_settings()
    if settings.is_production:
        print(
            "refusing to load the CSV fixture into a production database",
            file=sys.stderr,
        )
        return 1

    source = CsvCommoditySource(settings.products_csv_path)
    if not source.is_configured:
        print(f"product CSV not found: {settings.products_csv_path}", file=sys.stderr)
        return 1

    with Session(get_engine()) as session:
        result = ProductSyncService(session, source=source).run(replace=True)

    print(
        f"{result.processed} products loaded from {source.path.name} "
        f"(created {result.created}, skipped {result.skipped})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
