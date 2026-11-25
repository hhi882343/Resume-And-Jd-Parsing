"""Comprehensive unit tests for Pydantic v2 domain schemas."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas import (
    AnalysisPredictionCreate,
    AnalysisPredictionRead,
    AnalysisRunCreate,
    AnalysisRunRead,
    AnalyzedRequirement,
    AnalyzeRequest,
    AnalyzeResponse,
    CorrectionCreate,
    CorrectionRead,
    CorrectionRequest,
    CorrectionResponse,
    DpoPreferencePairExport,
    FeedbackStatsResponse,
    PolicyVersionCreate,
    PolicyVersionRead,
    PreferencePairCreate,
    PreferencePairRead,
    RequirementData,
)

# -----------------------------------------------------------------------------
# 1. RequirementData & AnalyzedRequirement Tests
# -----------------------------------------------------------------------------


def test_requirement_data_defaults():
    """Verify default values match the TypeScript EMPTY_REQUIREMENT contract."""
    req = RequirementData()
    assert req.job_title == "Not specified"
    assert req.job_status == "Unassigned"
    assert req.priority == "Not specified"
    assert req.mandatory_skills == []
    assert req.skills == []
    assert req.job_description == ""
    assert req.requirement_id.startswith("REQ-")


def test_requirement_data_camel_case_round_trip():
    """Verify bidirectional serialization with camelCase aliases emitted by Next.js."""
    ts_json = {
        "requirementId": "REQ-2026-10-29-ABC123",
        "jobTitle": "Senior Cloud Architect",
        "isInferredTitle": False,
        "clientLeadPocFrom": "Jane Doe <jane@company.com>",
        "clientPocFromCc": "cc@company.com",
        "internalPocTo": "Recruiter Bob",
        "requirementFrom": "ACME CORP",
        "demandReceivedDate": "29 October 2026",
        "closedDate": "Not specified",
        "openSince": "Today",
        "typeOfDemand": "Single",
        "jobStatus": "Unassigned",
        "priority": "HIGH",
        "relevantExperience": "Senior",
        "overallExperience": "8-12 Years",
        "qualificationCriteria": "B.Tech in CS",
        "employmentType": "FTE",
        "workMode": "Hybrid",
        "workTimings": "9 AM - 6 PM IST",
        "location": "Bangalore",
        "numberOfPositions": "2",
        "budgetCurrency": "INR",
        "monthlyBudget": "Not specified",
        "annualBudget": "28-35 LPA",
        "noticePeriod": "Immediate",
        "sla": "48 hours",
        "mandatorySkills": ["AWS", "Terraform", "Kubernetes"],
        "skills": ["Python", "Docker", "Go"],
        "jobDescription": "Architect scalable cloud platforms.",
    }

    # Deserialization from camelCase
    model = RequirementData.model_validate(ts_json)
    assert model.job_title == "Senior Cloud Architect"
    assert model.is_inferred_title is False
    assert model.client_lead_poc_from == "Jane Doe <jane@company.com>"
    assert model.annual_budget == "28-35 LPA"
    assert model.mandatory_skills == ["AWS", "Terraform", "Kubernetes"]

    # Serialization back to camelCase
    dumped = model.model_dump(by_alias=True)
    assert dumped["jobTitle"] == "Senior Cloud Architect"
    assert dumped["annualBudget"] == "28-35 LPA"
    assert dumped["mandatorySkills"] == ["AWS", "Terraform", "Kubernetes"]
    assert dumped == ts_json


def test_requirement_null_coercion():
    """Verify null values emitted by LLMs are gracefully converted to valid defaults."""
    raw_llm_output = {
        "jobTitle": "DevOps Engineer",
        "clientLeadPocFrom": None,
        "location": None,
        "annualBudget": None,
        "mandatorySkills": None,
        "skills": None,
        "jobDescription": None,
        "isInferredTitle": None,
    }

    model = RequirementData.model_validate(raw_llm_output)
    assert model.job_title == "DevOps Engineer"
    assert model.client_lead_poc_from == "Not specified"
    assert model.location == "Not specified"
    assert model.annual_budget == "Not specified"
    assert model.mandatory_skills == []
    assert model.skills == []
    assert model.job_description == ""
    assert model.is_inferred_title is None


def test_comma_delimited_skills_string_coercion():
    """Verify comma-delimited skill strings convert cleanly to string lists."""
    raw = {
        "jobTitle": "React Developer",
        "mandatorySkills": "React, TypeScript, Redux",
        "skills": "Jest, Tailwind",
    }
    model = RequirementData.model_validate(raw)
    assert model.mandatory_skills == ["React", "TypeScript", "Redux"]
    assert model.skills == ["Jest", "Tailwind"]


def test_analyzed_requirement_inheritance_and_constraints():
    """Verify AnalyzedRequirement inherits all 28 fields and enforces constraints."""
    analyzed = AnalyzedRequirement(
        job_title="Security Lead",
        requirement_title="Requirement #1: Security Lead",
        role_index=1,
        total_roles=3,
        extraction_source="Gemini (gemini-2.5-flash-lite)",
        last_reward_score=0.95,
    )
    assert analyzed.job_title == "Security Lead"
    assert analyzed.role_index == 1
    assert analyzed.total_roles == 3
    assert analyzed.last_reward_score == 0.95

    # Test invalid reward score (> 1.0)
    with pytest.raises(ValidationError):
        AnalyzedRequirement(role_index=1, total_roles=1, last_reward_score=1.5)

    # Test invalid role index (< 1)
    with pytest.raises(ValidationError):
        AnalyzedRequirement(role_index=0, total_roles=1)


# -----------------------------------------------------------------------------
# 2. API Request & Response Schema Tests
# -----------------------------------------------------------------------------


def test_analyze_request_validation():
    """Verify AnalyzeRequest validates minimum string length."""
    req = AnalyzeRequest(raw_jd_text="Looking for a Python Developer")
    assert req.raw_jd_text == "Looking for a Python Developer"

    # Empty string should fail validation
    with pytest.raises(ValidationError):
        AnalyzeRequest(raw_jd_text="")


def test_analyze_response_serialization():
    """Verify AnalyzeResponse camelCase serializes correctly."""
    role = AnalyzedRequirement(job_title="QA Engineer", role_index=1, total_roles=1)
    resp = AnalyzeResponse(
        total_requirements=1,
        requirements=[role],
        persisted=True,
    )
    dumped = resp.model_dump(by_alias=True)
    assert dumped["totalRequirements"] == 1
    assert len(dumped["requirements"]) == 1
    assert dumped["requirements"][0]["jobTitle"] == "QA Engineer"
    assert dumped["persisted"] is True


def test_correction_request_and_response():
    """Verify CorrectionRequest and CorrectionResponse payloads."""
    predicted = AnalyzedRequirement(job_title="Java Dev", role_index=1, total_roles=1)
    corrected = AnalyzedRequirement(job_title="Senior Java Dev", role_index=1, total_roles=1)

    req = CorrectionRequest(
        raw_jd_text="Raw JD text",
        predicted=predicted,
        corrected=corrected,
    )
    assert req.predicted.job_title == "Java Dev"
    assert req.corrected.job_title == "Senior Java Dev"

    resp = CorrectionResponse(
        success=True,
        saved=True,
        reward_score=0.925,
        field_rewards={"jobTitle": 0.8, "location": 1.0},
        preference_pair_created=True,
        message="Saved successfully",
        prediction_id="pred-123",
    )
    dumped = resp.model_dump(by_alias=True)
    assert dumped["rewardScore"] == 0.925
    assert dumped["preferencePairCreated"] is True
    assert dumped["predictionId"] == "pred-123"

    # Invalid reward score range (< 0.0)
    with pytest.raises(ValidationError):
        CorrectionResponse(
            saved=True,
            reward_score=-0.1,
            preference_pair_created=False,
            message="Error",
        )


def test_feedback_stats_response():
    """Verify FeedbackStatsResponse matches TypeScript GET /api/feedback/stats contract."""
    stats = FeedbackStatsResponse(
        total_analysis_runs=15,
        total_predictions=20,
        total_corrections=8,
        total_preference_pairs=6,
        avg_reward=0.914,
        policy_version="gemini-bootstrap",
        dpo_ready=False,
    )
    dumped = stats.model_dump(by_alias=True)
    assert dumped["totalAnalysisRuns"] == 15
    assert dumped["totalPredictions"] == 20
    assert dumped["totalCorrections"] == 8
    assert dumped["totalPreferencePairs"] == 6
    assert dumped["avgReward"] == 0.914
    assert dumped["dpoReady"] is False


# -----------------------------------------------------------------------------
# 3. Prisma Entity Schema Tests
# -----------------------------------------------------------------------------


def test_analysis_run_schemas():
    """Verify AnalysisRun read/write schemas."""
    create = AnalysisRunCreate(
        raw_jd_text="JD Content",
        model_used="gemini-2.5-flash-lite",
        chunk_count=2,
        status="success",
    )
    assert create.chunk_count == 2
    assert create.status == "success"

    read = AnalysisRunRead(
        id="run-uuid-1",
        raw_jd_text="JD Content",
        chunk_count=2,
        created_at=datetime.now(),
    )
    assert read.id == "run-uuid-1"

    # Test nullable fields for legacy row compatibility
    legacy = AnalysisRunCreate(
        raw_jd_text="Legacy JD",
        chunk_count=None,
        latency_ms=None,
        status=None,
    )
    assert legacy.chunk_count is None
    assert legacy.latency_ms is None
    assert legacy.status is None


def test_analysis_prediction_schemas():
    """Verify AnalysisPrediction read/write schemas."""
    create = AnalysisPredictionCreate(
        run_id="run-1",
        role_index=1,
        predicted_json=json.dumps({"jobTitle": "Frontend Engineer"}),
    )
    assert create.role_index == 1
    assert "Frontend Engineer" in create.predicted_json

    read = AnalysisPredictionRead(
        id="pred-1",
        run_id="run-1",
        role_index=1,
        predicted_json=create.predicted_json,
        created_at=datetime.now(),
    )
    assert read.id == "pred-1"


def test_correction_and_preference_pair_schemas():
    """Verify Correction and PreferencePair schemas."""
    corr_create = CorrectionCreate(
        prediction_id="pred-1",
        corrected_json=json.dumps({"jobTitle": "Fullstack Engineer"}),
        reward_score=0.88,
        field_rewards=json.dumps({"jobTitle": 0.8}),
    )
    assert corr_create.reward_score == 0.88

    corr_read = CorrectionRead(
        id="corr-1",
        prediction_id="pred-1",
        corrected_json=corr_create.corrected_json,
        reward_score=0.88,
        field_rewards=corr_create.field_rewards,
        corrected_at=datetime.now(),
    )
    assert corr_read.id == "corr-1"

    pair_create = PreferencePairCreate(
        prediction_id="pred-1",
        correction_id="corr-1",
        rejected_json=json.dumps({"jobTitle": "Frontend Engineer"}),
        chosen_json=json.dumps({"jobTitle": "Fullstack Engineer"}),
        reward_score=0.88,
        prompt="Extract structured requirement data from this JD",
    )
    assert pair_create.prediction_id == "pred-1"
    assert pair_create.correction_id == "corr-1"

    pair_read = PreferencePairRead(
        id="pair-1",
        prediction_id="pred-1",
        correction_id="corr-1",
        rejected_json=pair_create.rejected_json,
        chosen_json=pair_create.chosen_json,
        reward_score=0.88,
        created_at=datetime.now(),
    )
    assert pair_read.id == "pair-1"


def test_policy_version_and_dpo_export():
    """Verify PolicyVersion and DPO JSONL export row schemas."""
    pol_create = PolicyVersionCreate(
        version="gemini-bootstrap",
        base_model="gemini-2.5-flash-lite",
        avg_reward=0.92,
    )
    assert pol_create.version == "gemini-bootstrap"

    pol_read = PolicyVersionRead(
        id="pol-1",
        version=pol_create.version,
        base_model=pol_create.base_model,
        avg_reward=pol_create.avg_reward,
        created_at=datetime.now(),
    )
    assert pol_read.id == "pol-1"

    dpo_row = DpoPreferencePairExport(
        prompt="Extract structured data",
        rejected='{"jobTitle": "Engineer"}',
        chosen='{"jobTitle": "Senior Engineer"}',
        reward_score=0.93,
        prediction_id="pred-123",
    )
    dumped = dpo_row.model_dump(by_alias=True)
    assert dumped["rewardScore"] == 0.93
    assert dumped["predictionId"] == "pred-123"


def test_analyzed_requirement_email_headers_resilience():
    """Verify AnalyzedRequirement handles None, 'Not specified', and valid dicts gracefully."""
    # 1. Null / None email_headers
    req1 = AnalyzedRequirement(email_headers=None)
    assert req1.email_headers is None

    # 2. Coerced 'Not specified' string from legacy payloads or forms
    req2 = AnalyzedRequirement(email_headers="Not specified")
    assert req2.email_headers is None

    # 3. CamelCase alias with 'Not specified'
    req3 = AnalyzedRequirement.model_validate({"emailHeaders": "Not specified"})
    assert req3.email_headers is None

    # 4. Empty string
    req4 = AnalyzedRequirement(email_headers="")
    assert req4.email_headers is None

    # 5. Valid dictionary
    valid_headers = {
        "from": [{"name": "John", "email": "john@example.com"}],
        "to": [],
        "cc": [],
    }
    req5 = AnalyzedRequirement(email_headers=valid_headers)
    assert req5.email_headers == valid_headers

