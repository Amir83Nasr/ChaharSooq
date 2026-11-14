"""Parsina integration state — sync lock, bookkeeping, and connection config."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

SYNC_STATE_ID = 1


class ParsinaSyncState(Base):
    """Single row. `lock_until` is a compare-and-swap lock (portable to SQLite).

    Connection columns store the Parsina API credentials entered by the super
    admin in settings. They are nullable so env/secrets remain the fallback when
    no value has been saved in the database.
    """

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
    # Connection config (editable by owner in settings; env is the fallback).
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(512), nullable=True)
    org_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
