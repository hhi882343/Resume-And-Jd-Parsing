"""Validate Pydantic v2 domain schemas in app/schemas/ against TypeScript golden test fixtures.

Phase 3.5 Requirement:
- Loads every fixture's normalized outputs through RequirementData and AnalyzedRequirement.
- Uses camelCase alias parsing and bidirectional serialization.
- Any failing tests here are findings to report, not to silently mask or relax.
"""

import json
from pathlib import Path

import pytest

from app.schemas.correction import CorrectionResponse
from app.schemas.requirement import AnalyzedRequirement, RequirementData

FIXTURES_DIR = Path("tests/fixtures/golden")


@pytest.fixture(scope="module")
def normalize_fixtures():
    with open(FIXTURES_DIR / "normalize.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def reward_fixtures():
    with open(FIXTURES_DIR / "reward.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def reward_boundary_fixtures():
    with open(FIXTURES_DIR / "reward_boundary.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def overlay_fixtures():
    with open(FIXTURES_DIR / "correction_overlay.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def llm_boundary_fixtures():
    with open(FIXTURES_DIR / "llm_boundary.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def chunker_regex_fixtures():
    with open(FIXTURES_DIR / "chunker_regex.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def chunker_regex_traps_fixtures():
    with open(FIXTURES_DIR / "chunker_regex_traps.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def chunker_regex_traps2_fixtures():
    with open(FIXTURES_DIR / "chunker_regex_traps2.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_normalize_fixtures_conform_to_requirement_data(normalize_fixtures):
    """Verify that every normalized requirement from normalize.json cleanly parses via RequirementData."""
    for record in normalize_fixtures:
        rec_id = record["id"]
        norm_output = record["expected_output"]["normalized_requirement"]

        # Parse from TypeScript camelCase dictionary
        req = RequirementData.model_validate(norm_output)

        assert isinstance(req.job_title, str), f"[{rec_id}] job_title must be str"
        assert isinstance(req.mandatory_skills, list), f"[{rec_id}] mandatory_skills must be list"
        assert isinstance(req.skills, list), f"[{rec_id}] skills must be list"

        # Round-trip back to camelCase JSON
        dumped = req.model_dump(by_alias=True)
        assert "jobTitle" in dumped
        assert "mandatorySkills" in dumped
        assert "skills" in dumped
        assert "numberOfPositions" in dumped


def test_reward_fixtures_conform_to_schema_and_bounds(reward_fixtures):
    """Verify that reward fixture predicted/corrected payloads and scores conform to domain constraints."""
    for record in reward_fixtures:
        rec_id = record["id"]
        pred_dict = record["input"]["predicted"]
        corr_dict = record["input"]["corrected"]
        score = record["expected_output"]["reward_score"]

        # 1. Payloads must parse as RequirementData
        pred_req = RequirementData.model_validate(pred_dict)
        corr_req = RequirementData.model_validate(corr_dict)

        assert pred_req is not None, f"[{rec_id}] predicted payload failed validation"
        assert corr_req is not None, f"[{rec_id}] corrected payload failed validation"

        # 2. Reward score must strictly satisfy 0.0 <= score <= 1.0
        assert 0.0 <= score <= 1.0, f"[{rec_id}] score {score} out of [0.0, 1.0] bounds"

        # 3. Test through CorrectionResponse schema validation
        corr_resp = CorrectionResponse(
            success=True,
            saved=True,
            reward_score=score,
            field_rewards=record["expected_output"]["field_rewards"],
            preference_pair_created=record["expected_output"]["has_meaningful_diff"],
            message=record["description"],
        )
        assert corr_resp.reward_score == score


def test_reward_boundary_fixtures_conform_to_schema_and_bounds(reward_boundary_fixtures):
    """Verify that reward boundary fixture payloads and scores conform to domain constraints."""
    for record in reward_boundary_fixtures:
        rec_id = record["id"]
        pred_dict = record["input"]["predicted"]
        corr_dict = record["input"]["corrected"]
        score = record["expected_output"]["reward_score"]

        # 1. Payloads must parse as RequirementData
        pred_req = RequirementData.model_validate(pred_dict)
        corr_req = RequirementData.model_validate(corr_dict)

        assert pred_req is not None, f"[{rec_id}] predicted payload failed validation"
        assert corr_req is not None, f"[{rec_id}] corrected payload failed validation"

        # 2. Reward score must strictly satisfy 0.0 <= score <= 1.0
        assert 0.0 <= score <= 1.0, f"[{rec_id}] score {score} out of [0.0, 1.0] bounds"

        # 3. Test through CorrectionResponse schema validation
        corr_resp = CorrectionResponse(
            success=True,
            saved=True,
            reward_score=score,
            field_rewards=record["expected_output"]["field_rewards"],
            preference_pair_created=record["expected_output"]["has_meaningful_diff"],
            message=record["description"],
        )
        assert corr_resp.reward_score == score


def test_overlay_fixtures_conform_to_requirement_data(overlay_fixtures):
    """Verify that correction overlay fixture outputs conform to RequirementData."""
    for record in overlay_fixtures:
        rec_id = record["id"]
        overlaid_dict = record["expected_output"]

        req = RequirementData.model_validate(overlaid_dict)
        assert req is not None, f"[{rec_id}] Overlaid requirement failed validation"

        # Can also parse as AnalyzedRequirement
        analyzed = AnalyzedRequirement.model_validate(
            {
                **overlaid_dict,
                "requirementTitle": req.job_title,
                "roleIndex": 1,
                "totalRoles": 1,
            }
        )
        assert analyzed.role_index == 1


def test_llm_boundary_fixtures_conform_to_requirement_data(llm_boundary_fixtures):
    """Verify that raw LLM extraction boundary outputs conform to RequirementData."""
    for record in llm_boundary_fixtures:
        rec_id = record["id"]
        extracted = record["expected_output"]["extracted_data"]

        req = RequirementData.model_validate(extracted)
        assert req is not None, f"[{rec_id}] Extracted requirement failed validation"


def test_chunker_regex_augmented_fixtures_conform_to_schema(chunker_regex_fixtures):
    """Verify that regex-augmented outputs from chunker_regex.json conform to RequirementData."""
    for record in chunker_regex_fixtures:
        rec_id = record["id"]
        augmented = record["expected_output"]["regex_augmented"]

        req = RequirementData.model_validate(augmented)
        assert req is not None, f"[{rec_id}] Regex-augmented requirement failed validation"


def test_chunker_regex_traps_augmented_fixtures_conform_to_schema(
    chunker_regex_traps_fixtures,
):
    """Verify that regex-augmented outputs from chunker_regex_traps.json conform to RequirementData."""
    for record in chunker_regex_traps_fixtures:
        rec_id = record["id"]
        augmented = record["expected_output"]["regex_augmented"]

        req = RequirementData.model_validate(augmented)
        assert req is not None, f"[{rec_id}] Trap regex-augmented requirement failed validation"


def test_chunker_regex_traps_suite2_augmented_fixtures_conform_to_schema(
    chunker_regex_traps2_fixtures,
):
    """Verify that regex-augmented outputs from chunker_regex_traps2.json conform to RequirementData."""
    for record in chunker_regex_traps2_fixtures:
        rec_id = record["id"]
        augmented = record["expected_output"]["regex_augmented"]

        req = RequirementData.model_validate(augmented)
        assert req is not None, f"[{rec_id}] Trap 2 regex-augmented requirement failed validation"
