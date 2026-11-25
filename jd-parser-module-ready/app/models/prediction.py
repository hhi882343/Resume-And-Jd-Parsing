"""SQLAlchemy 2.0 ORM model for AnalysisPrediction."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.correction import Correction
    from app.models.preference_pair import PreferencePair
    from app.models.run import AnalysisRun


class AnalysisPrediction(Base):
    """Database model for an extracted role prediction within an AnalysisRun."""

    __tablename__ = "analysis_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chunk_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    chunk_content: Mapped[Optional[str]] = mapped_column(
        Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=True
    )
    predicted_json: Mapped[str] = mapped_column(
        Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    run: Mapped["AnalysisRun"] = relationship("AnalysisRun", back_populates="predictions")
    corrections: Mapped[List["Correction"]] = relationship(
        "Correction",
        back_populates="prediction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    preference_pairs: Mapped[List["PreferencePair"]] = relationship(
        "PreferencePair",
        back_populates="prediction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
