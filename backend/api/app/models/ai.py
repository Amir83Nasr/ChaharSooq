"""AI provider configuration — management-managed OpenAI-compatible endpoint."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

AI_CONFIG_ID = 1


class AIConfig(Base):
    """Single row holding the management-entered AI connection settings.

    The API key is write-only over the boundary: it is stored here so an
    administrator can rotate it from the panel, but it is never returned by any
    endpoint (only `api_key_set` is exposed). Empty strings keep the documented
    defaults; see `app.services.ai`. One model serves every AI feature.
    """

    __tablename__ = "ai_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
