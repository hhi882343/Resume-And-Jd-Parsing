"""Parity and unit tests for pure-Python regex augmentor (app/core/regex_augmentor.py).

Validates parity with TypeScript src/lib/jd-utils.ts regexAugment and extractCommonMetadata
across all golden fixtures in:
- tests/fixtures/golden/chunker_regex.json (18 records)
Asserts:
- exact key/value parity for common_metadata
- exact key/value parity for regex_augmented
- non-overwrite behavior on pre-populated fields
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from app.core.normalizer import to_requirement_data
from app.core.regex_augmentor import extract_common_metadata, regex_augment

FIXTURES_DIR = Path("tests/fixtures/golden")


def load_chunker_records():
    path = FIXTURES_DIR / "chunker_regex.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


CHUNKER_RECORDS = load_chunker_records()


@pytest.mark.parametrize("record", CHUNKER_RECORDS, ids=lambda r: r["id"])
def test_common_metadata_golden_parity(record: Dict[str, Any]):
    """Verify common metadata extraction parity against TypeScript golden outputs."""
    raw_text = record["input"]["raw_text"]
    expected_common = record["expected_output"]["common_metadata"]

    calc_common = extract_common_metadata(raw_text)

    for field, exp_val in expected_common.items():
        assert field in calc_common, f"[{record['id']}] Missing field {field} in common_metadata"
        assert calc_common[field] == exp_val, (
            f"[{record['id']}] common_metadata mismatch on {field}: "
            f"got {calc_common[field]!r}, expected {exp_val!r}"
        )


@pytest.mark.parametrize("record", CHUNKER_RECORDS, ids=lambda r: r["id"])
def test_regex_augmented_golden_parity(record: Dict[str, Any]):
    """Verify regex augmented requirement parity against TypeScript golden outputs."""
    raw_text = record["input"]["raw_text"]
    expected_aug = record["expected_output"]["regex_augmented"]

    empty_base = to_requirement_data({})
    calc_aug = regex_augment(raw_text, empty_base)

    for field, exp_val in expected_aug.items():
        assert field in calc_aug, f"[{record['id']}] Missing field {field} in regex_augmented"
        assert calc_aug[field] == exp_val, (
            f"[{record['id']}] regex_augmented mismatch on {field}: "
            f"got {calc_aug[field]!r}, expected {exp_val!r}"
        )


def test_regex_augment_does_not_clobber_existing_values():
    """Verify regex_augment does not overwrite already populated fields."""
    raw_text = """
    From: Recruiter <recruiter@acme.com>
    Subject: Senior React Dev @ Bangalore
    Headcount: 5
    Overall Exp - 8 years
    """
    initial = {
        "jobTitle": "Custom Preserved Title",
        "location": "Custom Preserved Location",
        "numberOfPositions": "10",
        "overallExperience": "12 years",
    }
    result = regex_augment(raw_text, initial)

    assert result["jobTitle"] == "Custom Preserved Title"
    assert result["location"] == "Custom Preserved Location"
    assert result["numberOfPositions"] == "10"
    assert result["overallExperience"] == "12 years"
    # Unpopulated fields should still be extracted
    assert result["clientLeadPocFrom"] == "Recruiter <recruiter@acme.com>"
    assert result["requirementFrom"] == "ACME"


def test_regex_budget_patterns():
    """Verify TPC rates, LPA, and IS2 budget parsing."""
    t1 = "TPC Rates - 1,20,000"
    r1 = regex_augment(t1, {})
    assert r1["monthlyBudget"] == "INR 1,20,000"
    assert r1["budgetCurrency"] == "INR"

    t2 = "Budget: 15 to 20 LPA"
    r2 = regex_augment(t2, {})
    assert r2["annualBudget"] == "15 to 20 LPA"
    assert r2["budgetCurrency"] == "INR"

    t3 = "Budget: 15 to 20 LPA\nIS2 - 18 LPA"
    r3 = regex_augment(t3, {})
    assert r3["annualBudget"] == "15 to 20 LPA (IS2: 18 LPA)"


def test_regex_work_mode_and_employment_type():
    """Verify work mode and employment type recognition."""
    assert (
        regex_augment("Hybrid mode (3 days in office)", {})["workMode"]
        == "Hybrid (3 days in office)"
    )
    assert regex_augment("Candidate must work on-site", {})["workMode"] == "On-site"
    assert regex_augment("Fully remote position", {})["workMode"] == "Remote"

    assert regex_augment("This is a Contract hire", {})["employmentType"] == "Contract"
    assert regex_augment("Type of Hire: FTE", {})["employmentType"] == "FTE"
    assert regex_augment("Employment Type: Sub-Con", {})["employmentType"] == "Sub-Con"
