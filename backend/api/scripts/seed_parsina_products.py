"""Load the Parsina CSV export into the development database.

Development only. Upserts the CSV catalog into the dev product mirror so the
dev UI shows the same shaped data as production without Parsina credentials.
Existing product rows keep their ids; rows absent from the CSV are deactivated
(never deleted), so competitor links and other product-bound data survive.
Run via `make db-seed-parsina` (which applies migrations first). The script
requires `DEPLOYMENT_ENV=development` and refuses Staging, Production, and
unknown identities.

The CSV path defaults to `<repo>/data/parsina.csv` and can be
overridden with `PRODUCTS_CSV_PATH`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.core.deployment import DEVELOPMENT, enforce_deployment_env
from app.integrations.parsina_csv import CsvCommoditySource
from app.services.sync import ProductSyncService


def main() -> int:
    enforce_deployment_env("seed_parsina_products", (DEVELOPMENT,))
    settings = get_settings()
    if settings.is_production:
        print(
            "refusing to load the CSV fixture into a production-mode database",
            file=sys.stderr,
        )
        return 1

    source = CsvCommoditySource(settings.products_csv_path)
    if not source.is_configured:
        print(f"product CSV not found: {settings.products_csv_path}", file=sys.stderr)
        return 1

    with Session(get_engine()) as session:
        result = ProductSyncService(session, source=source).run()

    print(
        f"{result.processed} products synced from {source.path.name} "
        f"(created {result.created}, updated {result.updated}, "
        f"deactivated {result.deactivated}, skipped {result.skipped})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
