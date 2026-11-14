"""Resolve and persist Parsina connection config (DB overrides env)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import ParsinaSettings, get_parsina_settings
from app.models import ParsinaSyncState
from app.repositories import SyncStateRepository


@dataclass(frozen=True)
class EffectiveParsina:
    settings: ParsinaSettings
    source: str  # "db" | "env" | "mixed" | "none"
    password_set: bool


def _db_has_connection(state: ParsinaSyncState) -> bool:
    values = (
        state.base_url,
        state.username,
        state.password,
        state.org_id,
        state.fiscal_year,
    )
    return any(value not in (None, "") for value in values)


def resolve_parsina_settings(
    session: Session, env: ParsinaSettings | None = None
) -> EffectiveParsina:
    """Merge DB-stored connection fields over the env/secrets config.

    A DB field wins when it is explicitly set (non-empty for strings, not null
    for integers). Unset DB fields fall back to the env config so existing
    deployments keep working without re-entering values in the UI.
    """
    env = env or get_parsina_settings()
    state = SyncStateRepository(session).ensure_state()

    base_url = (state.base_url or "").strip() or env.parsina_base_url
    username = (state.username or "").strip() or env.parsina_username
    password = state.password if state.password not in (None, "") else env.parsina_password
    org_id = state.org_id if state.org_id is not None else env.parsina_org_id
    fiscal_year = state.fiscal_year if state.fiscal_year is not None else env.parsina_year

    effective = ParsinaSettings(
        parsina_base_url=base_url,
        parsina_username=username,
        parsina_password=password or "",
        parsina_org_id=org_id,
        parsina_year=fiscal_year,
        parsina_ware_id=env.parsina_ware_id,
        parsina_sale_type_id=env.parsina_sale_type_id,
        parsina_timeout_seconds=env.parsina_timeout_seconds,
        parsina_sync_interval_minutes=env.parsina_sync_interval_minutes,
        parsina_sync_enabled=env.parsina_sync_enabled,
    )

    db_any = _db_has_connection(state)
    env_configured = env.is_configured
    db_configured = bool(
        (state.base_url or "").strip()
        and (state.username or "").strip()
        and state.password not in (None, "")
        and state.org_id is not None
        and state.fiscal_year is not None
    )

    if db_configured and env_configured:
        source = "db"
    elif db_any and env_configured:
        source = "mixed"
    elif db_any:
        source = "db"
    elif env_configured:
        source = "env"
    else:
        source = "none"

    return EffectiveParsina(settings=effective, source=source, password_set=bool(password))


def get_parsina_connection_view(session: Session) -> dict[str, object]:
    env = get_parsina_settings()
    resolved = resolve_parsina_settings(session, env)
    state = SyncStateRepository(session).ensure_state()
    # Show stored DB values for editable fields (falling back to env for display
    # when nothing stored yet), but never expose the password.
    return {
        "base_url": (state.base_url or "").strip() or env.base_url,
        "username": (state.username or "").strip() or env.parsina_username,
        "org_id": state.org_id if state.org_id is not None else env.parsina_org_id,
        "fiscal_year": state.fiscal_year if state.fiscal_year is not None else env.parsina_year,
        "password_set": resolved.password_set,
        "configured": resolved.settings.is_configured,
        "source": resolved.source,
    }


def update_parsina_connection(
    session: Session,
    *,
    base_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    org_id: int | None = None,
    fiscal_year: int | None = None,
    clear_password: bool = False,
) -> dict[str, object]:
    state = SyncStateRepository(session).ensure_state()
    if base_url is not None:
        state.base_url = base_url.strip() or None
    if username is not None:
        state.username = username.strip() or None
    if clear_password:
        state.password = None
    elif password is not None and password != "":
        state.password = password
    if org_id is not None:
        state.org_id = org_id
    if fiscal_year is not None:
        state.fiscal_year = fiscal_year
    session.commit()
    return get_parsina_connection_view(session)
