"""Shared pytest fixtures — in-memory DB + seeded admin client."""

import os
import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("APP_ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import Base, get_engine, reset_engine
from app.core.rate_limit import reset_rate_limits
from app.core.security import hash_password
from app.main import create_app
from app.models import Admin


@pytest.fixture()
def client() -> Iterator[TestClient]:
    reset_engine()
    reset_rate_limits()
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Admin(username="admin", password_hash=hash_password("secret123")))
        s.commit()
    with TestClient(create_app()) as c:
        yield c
