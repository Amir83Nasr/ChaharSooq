"""Env-managed owner bootstrap — create, password sync, single owner."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.core.security import hash_password, verify_password
from app.models import Admin
from app.models.auth import ROLE_ADMIN, ROLE_OWNER
from app.services.owner import OwnerBootstrapService


def test_bootstrap_demotes_other_owner_rows(client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as s:
        s.add(
            Admin(
                username="legacy",
                password_hash=hash_password("legacy-pass-123"),
                role=ROLE_OWNER,
            )
        )
        s.commit()

    with Session(engine) as s:
        OwnerBootstrapService(s).apply("root", "root-pass-123")
        s.commit()

    with Session(engine) as s:
        rows = {account.username: account for account in s.query(Admin).all()}
        assert rows["root"].role == ROLE_OWNER
        assert rows["legacy"].role == ROLE_ADMIN
        assert sum(1 for account in rows.values() if account.role == ROLE_OWNER) == 1


def test_bootstrap_creates_owner_and_syncs_password(client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as s:
        OwnerBootstrapService(s).apply("fresh", "fresh-pass-123")
        s.commit()

    with Session(engine) as s:
        rows = {account.username: account for account in s.query(Admin).all()}
        assert rows["fresh"].role == ROLE_OWNER
        # The pre-existing owner is demoted (single-owner invariant).
        assert rows["root"].role == ROLE_ADMIN
        assert verify_password(rows["fresh"].password_hash, "fresh-pass-123")

    # A changed env password re-hashes the same account instead of creating one.
    with Session(engine) as s:
        OwnerBootstrapService(s).apply("fresh", "new-fresh-pass-123")
        s.commit()

    with Session(engine) as s:
        rows = {account.username: account for account in s.query(Admin).all()}
        assert rows["fresh"].role == ROLE_OWNER
        assert verify_password(rows["fresh"].password_hash, "new-fresh-pass-123")
        assert not verify_password(rows["fresh"].password_hash, "fresh-pass-123")
        assert sum(1 for account in rows.values() if account.role == ROLE_OWNER) == 1
