"""Schemas for GET /api/feedback/stats response handling."""

from typing import Dict, Optional

from pydantic import Field

from app.schemas.base import CamelModel


class FeedbackStatsResponse(CamelModel):
    """Statistics returned by GET /api/feedback/stats tracking the RL feedback loop."""

    total_analysis_runs: int = Field(default=0, ge=0, description="Total analysis runs processed")
    total_predictions: int = Field(default=0, ge=0, description="Total per-role predictions logged")
    total_corrections: int = Field(
        default=0, ge=0, description="Total recruiter corrections received"
    )
    total_preference_pairs: int = Field(
        default=0, ge=0, description="Total DPO preference pairs collected"
    )
    avg_reward: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Average reward score across all corrections"
    )
    policy_version: str = Field(
        default="gemini-bootstrap", description="Active RL policy version identifier"
    )
    dpo_ready: bool = Field(
        default=False, description="True when preference pairs reach fine-tuning threshold (50+)"
    )

    # Extended metrics for Streamlit UI dashboards
    field_avgs: Optional[Dict[str, float]] = Field(
        default=None, description="Average accuracy per field"
    )
    dpo_target: int = Field(default=50, description="Target pair count for initial DPO pilot")
    dpo_progress: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Progress ratio toward 50 pairs goal"
    )
