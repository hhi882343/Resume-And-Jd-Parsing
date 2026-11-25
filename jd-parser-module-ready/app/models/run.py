"""SQLAlchemy 2.0 ORM model for AnalysisRun."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.prediction import AnalysisPrediction


class AnalysisRun(Base):
    """Database model recording a complete JD analysis run."""

    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_jd_text: Mapped[str] = mapped_column(
        Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False
    )
    model_used: Mapped[Optional[str]] = mapped_column(String(191), nullable=True)
    policy_version: Mapped[str] = mapped_column(
        String(191), default="gemini-bootstrap", nullable=False
    )
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    predictions: Mapped[List["AnalysisPrediction"]] = relationship(
        "AnalysisPrediction",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
