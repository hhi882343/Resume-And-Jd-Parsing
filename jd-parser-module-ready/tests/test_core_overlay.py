"""Parity and unit tests for pure-Python correction overlay (app/core/overlay.py).

Validates parity with TypeScript overlay logic from src/app/api/analyze/route.ts lines 73-94
across all golden fixtures in tests/fixtures/golden/correction_overlay.json (12 records).

Asserts:
- exact key-by-key and value-by-value equality with expected_output
- exact branch order and preserved TS quirks:
  * Branch 3 can assign an empty correction value over an empty LLM value
  * An empty LLM array [] is NOT counted as empty in Branch 3
  * Empty arrays in the correction never overwrite (Branch 1 requires length > 0)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from app.core.overlay import apply_correction_overlay
from app.schemas.requirement import RequirementData

FIXTURES_DIR = Path("tests/fixtures/golden")


def load_overlay_records():
    path = FIXTURES_DIR / "correction_overlay.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


OVERLAY_RECORDS = load_overlay_records()


@pytest.mark.parametrize("record", OVERLAY_RECORDS, ids=lambda r: r["id"])
def test_overlay_golden_fixtures(record: Dict[str, Any]):
    """Parametrized parity test for each record in correction_overlay.json."""
    fresh_llm = record["input"]["fresh_llm_result"]
    prior_corr = record["input"]["prior_correction"]
    expected = record["expected_output"]
    rec_id = record["id"]

    calc_overlaid = apply_correction_overlay(fresh_llm, prior_corr)

    # 1. Output must parse cleanly into RequirementData
    req = RequirementData.model_validate(calc_overlaid)
    assert req is not None, f"[{rec_id}] Result failed RequirementData validation"

    # 2. Every single field must match the expected golden output exactly
    for field_name, exp_val in expected.items():
        assert field_name in calc_overlaid, (
            f"[{rec_id}] Missing field {field_name} in overlaid result"
        )
        assert calc_overlaid[field_name] == exp_val, (
            f"[{rec_id}] Field {field_name} mismatch: "
            f"got {calc_overlaid[field_name]!r}, expected {exp_val!r}"
        )


def test_overlay_preserved_quirks():
    """Verify specific preserved TypeScript quirks from route.ts lines 73-94."""
    # Quirks 1 & 3: Empty array in correction never overwrites (Branch 1 length > 0)
    llm = {
        "jobTitle": "Backend Engineer",
        "mandatorySkills": ["Python", "FastAPI"],
        "location": "Not specified",
        "workMode": "",
    }
    corr_empty_skills = {
        "mandatorySkills": [],  # Empty array in correction: must NOT overwrite
    }
    res1 = apply_correction_overlay(llm, corr_empty_skills)
    assert res1["mandatorySkills"] == ["Python", "FastAPI"]

    # Quirk 2: An empty LLM array [] is NOT counted as empty in Branch 3
    # In Branch 3: llmVal === "Not specified" || llmVal === "" || llmVal === undefined
    # An empty array [] !== "Not specified", !== "", !== undefined
    llm_empty_list = {
        "jobTitle": "Backend Engineer",
        "skills": [],
    }
    corr_empty_str = {
        "skills": "",  # string empty misses Branch 1 & 2; Branch 3 checks llmVal which is [], so doesn't trigger!
    }
    res2 = apply_correction_overlay(llm_empty_list, corr_empty_str)
    assert res2["skills"] == []

    # Quirk 1: Branch 3 CAN assign an empty correction value over an empty LLM value
    corr_assign_empty = {
        "location": "",  # misses Branch 2; Branch 3 triggers because llm["location"] == "Not specified"
        "workMode": "Not specified",  # misses Branch 2; Branch 3 triggers because llm["workMode"] == ""
    }
    res3 = apply_correction_overlay(llm, corr_assign_empty)
    assert res3["location"] == ""
    assert res3["workMode"] == "Not specified"


def test_overlay_with_pydantic_models():
    """Verify apply_correction_overlay handles RequirementData instances directly."""
    fresh = RequirementData(
        job_title="Junior Analyst",
        location="London",
        mandatory_skills=["Excel"],
        skills=["SQL"],
    )
    corr = RequirementData(
        job_title="Senior Data Analyst",
        location="Not specified",
        mandatory_skills=["Python", "SQL"],
        skills=[],
    )
    res = apply_correction_overlay(fresh, corr)
    assert res["jobTitle"] == "Senior Data Analyst"
    assert res["location"] == "London"
    assert res["mandatorySkills"] == ["Python", "SQL"]
