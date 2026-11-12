"""Delete all products from the development database.

Development only. Removes the seeded/test catalog (including the CSV mirror)
so the dev UI starts from an empty product list. Competitor listings are
deleted first (they reference products); sync-state counters are reset so the
status panel no longer reports the previous seed run.
Run via `make db-clear-products` (which starts postgres first). The script
requires `DEPLOYMENT_ENV=development`; Staging, Production, and unknown
identities are refused before a connection is opened.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.core.deployment import DEVELOPMENT, enforce_deployment_env
from app.models import ParsinaSyncState
from app.models.catalog import Product
from app.models.competitor import CompetitorListing
from app.models.parsina import SYNC_STATE_ID


def main() -> int:
    enforce_deployment_env("clear_products", (DEVELOPMENT,))
    settings = get_settings()
    if settings.is_production:
        print(
            "refusing to clear products in a production-mode database",
            file=sys.stderr,
        )
        return 1

    with Session(get_engine()) as session:
        listings: int = session.scalar(select(func.count()).select_from(CompetitorListing)) or 0
        removed: int = session.scalar(select(func.count()).select_from(Product)) or 0
        session.execute(delete(CompetitorListing))
        session.execute(delete(Product))
        state = session.get(ParsinaSyncState, SYNC_STATE_ID)
        if state is None:
            state = ParsinaSyncState(id=SYNC_STATE_ID)
            session.add(state)
        state.lock_until = None
        state.running_since = None
        state.last_attempt_at = None
        state.last_success_at = None
        state.last_error = None
        state.last_processed = 0
        state.last_created = 0
        state.last_updated = 0
        state.last_deactivated = 0
        state.last_skipped = 0
        session.commit()

    print(f"cleared {removed} products and {listings} competitor listings (dev only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
