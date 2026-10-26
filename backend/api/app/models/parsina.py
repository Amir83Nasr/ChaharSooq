"""Parsina integration state — sync lock + last attempt/success bookkeeping."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

SYNC_STATE_ID = 1


class ParsinaSyncState(Base):
    """Single row. `lock_until` is a compare-and-swap lock (portable to SQLite)."""

    __tablename__ = "parsina_sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lock_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    running_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_deactivated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
