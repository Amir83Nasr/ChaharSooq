"""Account model — owner, admins, and read-only viewers share one login table."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import utcnow

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"
ROLES = (ROLE_OWNER, ROLE_ADMIN, ROLE_VIEWER)
# Roles the panel may assign when creating an account. The owner itself is
# env-managed (see app/services/owner.py) and never created from the panel.
ASSIGNABLE_ROLES = (ROLE_ADMIN, ROLE_VIEWER)


class Admin(Base):
    """One login account, seeded from the env owner or created in the panel.

    ``role`` decides what the account may do: ``owner`` manages everything
    (including admins), ``admin`` manages shop data and viewers, ``viewer``
    is read-only.
    """

    __tablename__ = "admins"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'viewer')", name="ck_admins_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ROLE_ADMIN, server_default=ROLE_ADMIN
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
