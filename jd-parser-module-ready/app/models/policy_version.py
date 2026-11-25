"""SQLAlchemy 2.0 ORM model for PolicyVersion."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PolicyVersion(Base):
    """Database model for tracking RL policy iteration versions and deployment state."""

    __tablename__ = "policy_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    version: Mapped[str] = mapped_column(String(191), nullable=False, unique=True)
    base_model: Mapped[str] = mapped_column(String(191), nullable=False)
    avg_reward: Mapped[Optional[float]] = mapped_column(
        Float(53).with_variant(mysql.DOUBLE(), "mysql"), nullable=True
    )
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
