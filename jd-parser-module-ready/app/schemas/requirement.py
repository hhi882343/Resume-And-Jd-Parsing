"""Requirement domain schemas derived from TypeScript definitions in src/types/requirement.ts."""

import random
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator, model_validator

from app.core.clock import local_now
from app.schemas.base import CamelModel

NOT_SPECIFIED = "Not specified"


def generate_requirement_id() -> str:
    """Generate requirement identifier formatted like REQ-YYYY-MM-DD-SEQ."""
    now = local_now()
    seq = random.randint(100, 999)
    return f"REQ-{now.strftime('%Y-%m-%d')}-{seq}"


class RequirementData(CamelModel):
    """Structured ATS recruitment requirement data schema (exact 28 core fields + metadata)."""

    requirement_id: str = Field(default_factory=generate_requirement_id)
    job_title: str = NOT_SPECIFIED
    is_inferred_title: Optional[bool] = None
    client_lead_poc_from: str = NOT_SPECIFIED
    client_poc_from_cc: str = NOT_SPECIFIED
    internal_poc_to: str = NOT_SPECIFIED
    requirement_from: str = NOT_SPECIFIED
    demand_received_date: str = NOT_SPECIFIED
    closed_date: str = NOT_SPECIFIED
    open_since: str = NOT_SPECIFIED
    type_of_demand: str = NOT_SPECIFIED
    job_status: str = "Unassigned"
    priority: str = NOT_SPECIFIED
    relevant_experience: str = NOT_SPECIFIED
    overall_experience: str = NOT_SPECIFIED
    qualification_criteria: str = NOT_SPECIFIED
    employment_type: str = NOT_SPECIFIED
    work_mode: str = NOT_SPECIFIED
    work_timings: str = NOT_SPECIFIED
    location: str = NOT_SPECIFIED
    number_of_positions: str = NOT_SPECIFIED
    budget_currency: str = NOT_SPECIFIED
    monthly_budget: str = NOT_SPECIFIED
    annual_budget: str = NOT_SPECIFIED
    notice_period: str = NOT_SPECIFIED
    sla: str = NOT_SPECIFIED
    mandatory_skills: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    job_description: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_nulls_and_lists(cls, data: Any) -> Any:
        """Coerce nulls from raw LLM outputs or external inputs to valid defaults."""
        if not isinstance(data, dict):
            return data

        cleaned = dict(data)
        list_keys = {"mandatorySkills", "mandatory_skills", "skills"}
        nullable_keys = {
            "isInferredTitle",
            "is_inferred_title",
            "extractionSource",
            "extraction_source",
            "correctionApplied",
            "correction_applied",
            "runId",
            "run_id",
            "predictionId",
            "prediction_id",
            "policyVersion",
            "policy_version",
            "lastRewardScore",
            "last_reward_score",
            "feedbackSaved",
            "feedback_saved",
            "emailHeaders",
            "email_headers",
        }

        for k, v in list(cleaned.items()):
            if k in {"emailHeaders", "email_headers"} and (
                v is None or v in (NOT_SPECIFIED, "Not specified", "", "null")
            ):
                cleaned[k] = None
            elif v is None:
                if k in list_keys:
                    cleaned[k] = []
                elif k in nullable_keys:
                    cleaned[k] = None
                elif k in {"jobStatus", "job_status"}:
                    cleaned[k] = "Unassigned"
                elif k in {"jobDescription", "job_description"}:
                    cleaned[k] = ""
                else:
                    cleaned[k] = NOT_SPECIFIED
            elif k in list_keys and isinstance(v, str):
                cleaned[k] = [s.strip() for s in v.split(",") if s.strip()]

        return cleaned


class AnalyzedRequirement(RequirementData):
    """Extension of RequirementData returned by /api/analyze and displayed on UI cards."""

    requirement_title: str = "Single Requirement"
    role_index: int = Field(default=1, ge=1)
    total_roles: int = Field(default=1, ge=1)
    extraction_source: Optional[str] = None
    correction_applied: Optional[bool] = None
    run_id: Optional[str] = None
    prediction_id: Optional[str] = None
    policy_version: Optional[str] = None
    last_reward_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    feedback_saved: Optional[bool] = None
    email_headers: Optional[Dict[str, List[Dict[str, str]]]] = None

    @field_validator("email_headers", mode="before")
    @classmethod
    def validate_email_headers(cls, v: Any) -> Optional[Dict[str, List[Dict[str, str]]]]:
        if v in (None, NOT_SPECIFIED, "Not specified", "", "null"):
            return None
        if isinstance(v, dict):
            return v
        return None


EMPTY_REQUIREMENT: Dict[str, Any] = {
    "requirementId": NOT_SPECIFIED,
    "jobTitle": NOT_SPECIFIED,
    "clientLeadPocFrom": NOT_SPECIFIED,
    "clientPocFromCc": NOT_SPECIFIED,
    "internalPocTo": NOT_SPECIFIED,
    "requirementFrom": NOT_SPECIFIED,
    "demandReceivedDate": NOT_SPECIFIED,
    "closedDate": NOT_SPECIFIED,
    "openSince": NOT_SPECIFIED,
    "typeOfDemand": NOT_SPECIFIED,
    "jobStatus": "Unassigned",
    "priority": NOT_SPECIFIED,
    "relevantExperience": NOT_SPECIFIED,
    "overallExperience": NOT_SPECIFIED,
    "qualificationCriteria": NOT_SPECIFIED,
    "employmentType": NOT_SPECIFIED,
    "workMode": NOT_SPECIFIED,
    "workTimings": NOT_SPECIFIED,
    "location": NOT_SPECIFIED,
    "numberOfPositions": NOT_SPECIFIED,
    "budgetCurrency": NOT_SPECIFIED,
    "monthlyBudget": NOT_SPECIFIED,
    "annualBudget": NOT_SPECIFIED,
    "noticePeriod": NOT_SPECIFIED,
    "sla": NOT_SPECIFIED,
    "mandatorySkills": [],
    "skills": [],
    "jobDescription": "",
}
