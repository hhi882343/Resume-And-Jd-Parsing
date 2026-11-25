"""Pydantic read/write domain schemas for the five Prisma entities."""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import CamelModel

# ---------------------------------------------------------------------------
# 1. AnalysisRun
# ---------------------------------------------------------------------------


class AnalysisRunBase(CamelModel):
    """Base schema for an analysis run."""

    raw_jd_text: str = Field(min_length=1)
    model_used: Optional[str] = None
    policy_version: str = "gemini-bootstrap"
    chunk_count: Optional[int] = Field(default=None, ge=1)
    latency_ms: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = "success"


class AnalysisRunCreate(AnalysisRunBase):
    """Schema for creating a new AnalysisRun."""

    id: Optional[str] = None


class AnalysisRunRead(AnalysisRunBase):
    """Schema for reading a persisted AnalysisRun."""

    id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# 2. AnalysisPrediction
# ---------------------------------------------------------------------------


class AnalysisPredictionBase(CamelModel):
    """Base schema for an individual extracted role prediction within a run."""

    run_id: str
    role_index: int = Field(default=1, ge=1)
    chunk_title: Optional[str] = None
    chunk_content: Optional[str] = None
    predicted_json: str = Field(description="Serialized RequirementData JSON payload")


class AnalysisPredictionCreate(AnalysisPredictionBase):
    """Schema for creating a new AnalysisPrediction."""

    id: Optional[str] = None


class AnalysisPredictionRead(AnalysisPredictionBase):
    """Schema for reading a persisted AnalysisPrediction."""

    id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# 3. Correction
# ---------------------------------------------------------------------------


class CorrectionBase(CamelModel):
    """Base schema for a human recruiter correction record."""

    prediction_id: str
    corrected_json: str = Field(description="Serialized corrected RequirementData JSON payload")
    reward_score: float = Field(ge=0.0, le=1.0)
    field_rewards: str = Field(description="JSON string representing field-level reward mapping")


class CorrectionCreate(CorrectionBase):
    """Schema for creating a new Correction."""

    id: Optional[str] = None


class CorrectionRead(CorrectionBase):
    """Schema for reading a persisted Correction."""

    id: str
    corrected_at: datetime


# ---------------------------------------------------------------------------
# 4. PreferencePair
# ---------------------------------------------------------------------------


class PreferencePairBase(CamelModel):
    """Base schema for a DPO preference pair { rejected, chosen }."""

    prediction_id: str
    correction_id: str
    rejected_json: str = Field(description="Model output rejected JSON")
    chosen_json: str = Field(description="Human ground truth chosen JSON")
    reward_score: float = Field(ge=0.0, le=1.0)
    prompt: Optional[str] = None


class PreferencePairCreate(PreferencePairBase):
    """Schema for creating a new PreferencePair."""

    id: Optional[str] = None


class PreferencePairRead(PreferencePairBase):
    """Schema for reading a persisted PreferencePair."""

    id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# 5. PolicyVersion
# ---------------------------------------------------------------------------


class PolicyVersionBase(CamelModel):
    """Base schema for an RL policy version iteration."""

    version: str
    base_model: str
    avg_reward: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    deployed_at: Optional[datetime] = None


class PolicyVersionCreate(PolicyVersionBase):
    """Schema for creating a new PolicyVersion."""

    id: Optional[str] = None


class PolicyVersionRead(PolicyVersionBase):
    """Schema for reading a persisted PolicyVersion."""

    id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# DPO Export Format Schema
# ---------------------------------------------------------------------------


class DpoPreferencePairExport(CamelModel):
    """Line format for data/dpo-preference-pairs.jsonl read by Hugging Face TRL."""

    prompt: str
    rejected: str
    chosen: str
    reward_score: float = Field(ge=0.0, le=1.0)
    prediction_id: str
