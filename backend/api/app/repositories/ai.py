"""AI configuration repository — direct AIConfig queries."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.ai import AI_CONFIG_ID, AIConfig


class AIConfigRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> AIConfig | None:
        return self._session.get(AIConfig, AI_CONFIG_ID)

    def ensure(self) -> AIConfig:
        row = self.get()
        if row is None:
            row = AIConfig(
                id=AI_CONFIG_ID,
                base_url="",
                api_key=None,
                model_id="",
                system_prompt="",
            )
            self._session.add(row)
            self._session.flush()
        return row
