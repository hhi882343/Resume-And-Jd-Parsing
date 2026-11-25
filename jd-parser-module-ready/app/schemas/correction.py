"""Schemas for POST /api/corrections request and response handling."""

from typing import Dict, Optional

from pydantic import Field

from app.schemas.base import CamelModel
from app.schemas.requirement import AnalyzedRequirement


class CorrectionRequest(CamelModel):
    """Payload for POST /api/corrections containing recruiter ground-truth adjustments."""

    raw_jd_text: str = Field(..., min_length=1, description="Original unparsed JD text")
    predicted: AnalyzedRequirement = Field(
        ..., description="Initial model prediction before human modification"
    )
    corrected: AnalyzedRequirement = Field(..., description="Human corrected requirement state")


class CorrectionResponse(CamelModel):
    """Response returned after computing rewards and persisting corrections."""

    success: bool = True
    saved: bool = Field(
        description="True if human corrections differed meaningfully from prediction"
    )
    reward_score: float = Field(
        ge=0.0, le=1.0, description="Weighted reward score between prediction and correction"
    )
    field_rewards: Dict[str, float] = Field(
        default_factory=dict, description="Field-level match scores (0.0 to 1.0)"
    )
    preference_pair_created: bool = Field(
        description="True if a DPO preference pair was logged for model fine-tuning"
    )
    message: str = Field(description="Human-readable status summary")
    run_id: Optional[str] = None
    prediction_id: Optional[str] = None
    correction_id: Optional[str] = None
