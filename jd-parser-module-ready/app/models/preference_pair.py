"""SQLAlchemy 2.0 ORM model for PreferencePair."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.correction import Correction
    from app.models.prediction import AnalysisPrediction


class PreferencePair(Base):
    """Database model for DPO preference pairs { rejected, chosen }."""

    __tablename__ = "preference_pairs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prediction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_predictions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    correction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("corrections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    rejected_json: Mapped[str] = mapped_column(
        Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False
    )
    chosen_json: Mapped[str] = mapped_column(
        Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False
    )
    reward_score: Mapped[float] = mapped_column(
        Float(53).with_variant(mysql.DOUBLE(), "mysql"), nullable=False
    )
    prompt: Mapped[Optional[str]] = mapped_column(
        Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    prediction: Mapped["AnalysisPrediction"] = relationship(
        "AnalysisPrediction", back_populates="preference_pairs"
    )
    correction: Mapped["Correction"] = relationship("Correction", back_populates="preference_pair")
