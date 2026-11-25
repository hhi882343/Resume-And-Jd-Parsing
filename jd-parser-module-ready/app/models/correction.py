"""SQLAlchemy 2.0 ORM model for Correction."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.prediction import AnalysisPrediction
    from app.models.preference_pair import PreferencePair


class Correction(Base):
    """Database model for recruiter ground-truth corrections and reward evaluations."""

    __tablename__ = "corrections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prediction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_predictions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    corrected_json: Mapped[str] = mapped_column(
        Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False
    )
    reward_score: Mapped[float] = mapped_column(
        Float(53).with_variant(mysql.DOUBLE(), "mysql"), nullable=False
    )
    field_rewards: Mapped[str] = mapped_column(
        Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False
    )
    corrected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    prediction: Mapped["AnalysisPrediction"] = relationship(
        "AnalysisPrediction", back_populates="corrections"
    )
    preference_pair: Mapped[Optional["PreferencePair"]] = relationship(
        "PreferencePair",
        back_populates="correction",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
