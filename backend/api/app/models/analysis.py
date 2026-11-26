"""Latest AI analysis report per product — one replaceable row."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import utcnow


class ProductAnalysisReport(Base):
    """The last complete AI report for a product.

    A new analysis replaces the row; the owner deletes it explicitly. The FK
    cascade keeps reports from outliving a product.
    """

    __tablename__ = "product_analysis_reports"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
