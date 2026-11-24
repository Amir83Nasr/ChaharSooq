"""Settings repositories — direct Setting/SuggestedPriceFormula queries."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Setting, SuggestedPriceFormula


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> Setting | None:
        return self._session.get(Setting, key)

    def upsert(self, key: str, value: str) -> Setting:
        row = self._session.get(Setting, key)
        if row is None:
            row = Setting(key=key, value=value)
            self._session.add(row)
        else:
            row.value = value
        self._session.flush()
        return row


class SuggestedPriceFormulaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_ordered(self) -> list[SuggestedPriceFormula]:
        return list(
            self._session.scalars(
                select(SuggestedPriceFormula).order_by(SuggestedPriceFormula.top_group)
            ).all()
        )

    def get_map(self) -> dict[str, SuggestedPriceFormula]:
        return {
            row.top_group: row for row in self._session.scalars(select(SuggestedPriceFormula)).all()
        }

    def add(self, row: SuggestedPriceFormula) -> SuggestedPriceFormula:
        self._session.add(row)
        self._session.flush()
        return row

    def update_weight(self, row: SuggestedPriceFormula, weight: Decimal) -> None:
        row.weight = weight
        self._session.flush()

    def delete(self, row: SuggestedPriceFormula) -> None:
        self._session.delete(row)
        self._session.flush()
