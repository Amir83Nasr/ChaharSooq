"""Schema guards that only surface on a real PostgreSQL backend.

`Base.metadata.create_all` (tests, `scripts/seed_admin.py`) never runs
Alembic, so anything a migration installs by hand must be installed by the
metadata listener too — CI's Postgres run is what proves it.
"""

import pytest
from sqlalchemy import text

from app.core.database import Base, get_engine, reset_engine


def test_create_all_installs_pg_trgm() -> None:
    """`0012_search_indexes` puts trigram GIN indexes on `products`.

    Regression guard: the model declared `gin_trgm_ops` indexes without
    installing the extension, so `create_all` failed on PostgreSQL with
    `operator class "gin_trgm_ops" does not exist for access method "gin"`
    and every backend CI test errored at setup.
    """
    reset_engine()
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        pytest.skip("pg_trgm is PostgreSQL-only; SQLite runs plain B-tree indexes")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        installed = conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')")
        ).scalar_one()
    assert installed is True
    # Leave a clean slate for the `client` fixture that runs next.
    Base.metadata.drop_all(engine)
