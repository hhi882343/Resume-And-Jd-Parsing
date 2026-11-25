"""Schemas for POST /api/analyze request and response handling."""

from typing import List, Optional

from pydantic import Field

from app.schemas.base import CamelModel
from app.schemas.requirement import AnalyzedRequirement


class AnalyzeRequest(CamelModel):
    """Payload for POST /api/analyze."""

    raw_jd_text: str = Field(
        ...,
        min_length=1,
        description="Raw job description, recruiter email, or vendor requirement text",
    )


class AnalyzeResponse(CamelModel):
    """Successful response payload from POST /api/analyze."""

    total_requirements: int = Field(ge=0, description="Total number of distinct roles extracted")
    requirements: List[AnalyzedRequirement] = Field(
        default_factory=list, description="List of extracted requirements"
    )
    persisted: bool = Field(
        default=True, description="Whether the analysis run was saved to the learning database"
    )


class AnalyzeRateLimitResponse(CamelModel):
    """Error payload returned when LLM API rate limits are encountered (HTTP 429)."""

    error: str = Field(default="API rate limit exceeded")
    details: Optional[str] = None
    is_rate_limit: bool = True


class AnalyzeErrorResponse(CamelModel):
    """Generic error payload for failed analysis (HTTP 400 or 500)."""

    error: str
