"""Database engine / session wiring. SQLAlchemy 2.x style only."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def _build_engine() -> Engine:
    from app.core.config import get_settings

    url = get_settings().database_url
    if url.startswith("sqlite"):
        return create_engine(
            url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    return create_engine(url, pool_pre_ping=True)


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = _build_engine()
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    """Test-only: drop cached engine so a new DATABASE_URL takes effect."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def get_session() -> Iterator[Session]:
    """Yield a request-scoped session from the shared factory.

    The factory is built once per engine (see ``get_engine``) and reused
    across requests instead of re-creating a ``sessionmaker`` per call.
    Commit/rollback semantics are unchanged.
    """
    get_engine()
    if _SessionLocal is None:  # pragma: no cover — engine always initializes the factory
        raise RuntimeError("database engine is not initialized")
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_readonly_session() -> Iterator[Session]:
    """Yield a read-only request session — never commits.

    GET handlers must use this so a stray attribute change can never be
    flushed to the database by the shared commit in ``get_session``.
    """
    get_engine()
    if _SessionLocal is None:  # pragma: no cover — engine always initializes the factory
        raise RuntimeError("database engine is not initialized")
    session = _SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()
