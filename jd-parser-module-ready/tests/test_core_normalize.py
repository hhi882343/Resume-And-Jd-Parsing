"""Parity and unit tests for pure-Python ATS normalization (app/core/normalize.py).

Validates parity with TypeScript src/lib/jd-utils.ts across all golden fixtures in:
- tests/fixtures/golden/normalize.json (16 records)

Asserts:
- exact string equality for single_field_normalized
- exact list equality for skills_normalized
- exact mapping for mapped_experience
- exact extraction for extracted_company
- exact field-by-field equality for normalized_requirement
- JS-equivalent whitespace trimming and collapsing
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

import pytest

from app.core.normalize import (
    NOT_SPECIFIED,
    company_from_email,
    extract_job_description_section,
    format_open_since,
    is_generic_job_title,
    map_relevant_experience,
    merge_inherited_fields,
    normalize,
    normalize_skills,
    resolve_job_title,
    split_skill_list,
    to_requirement_data,
)

FIXTURES_DIR = Path("tests/fixtures/golden")


def load_normalize_records():
    path = FIXTURES_DIR / "normalize.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


NORMALIZE_RECORDS = load_normalize_records()


@pytest.mark.parametrize("record", NORMALIZE_RECORDS, ids=lambda r: r["id"])
def test_normalize_golden_fixtures(record: Dict[str, Any]):
    """Parametrized test for each record in normalize.json."""
    inp = record["input"]
    expected = record["expected_output"]
    rec_id = record["id"]

    # 1. Single field normalization
    job_title_in = inp.get("jobTitle")
    calc_single = normalize(job_title_in)
    assert calc_single == expected["single_field_normalized"], (
        f"[{rec_id}] single_field_normalized mismatch: "
        f"got {calc_single!r}, expected {expected['single_field_normalized']!r}"
    )

    # 2. Skills normalization
    skills_in = inp.get("mandatorySkills")
    calc_skills = normalize_skills(skills_in)
    assert calc_skills == expected["skills_normalized"], (
        f"[{rec_id}] skills_normalized mismatch: "
        f"got {calc_skills!r}, expected {expected['skills_normalized']!r}"
    )

    # 3. Experience mapping (when input is string)
    if isinstance(inp.get("overallExperience"), str):
        calc_exp = map_relevant_experience(inp["overallExperience"])
        assert calc_exp == expected["mapped_experience"], (
            f"[{rec_id}] mapped_experience mismatch: "
            f"got {calc_exp!r}, expected {expected['mapped_experience']!r}"
        )

    # 4. Company from email (when input is string)
    if isinstance(inp.get("clientLeadPocFrom"), str):
        calc_company = company_from_email(inp["clientLeadPocFrom"])
        assert calc_company == expected["extracted_company"], (
            f"[{rec_id}] extracted_company mismatch: "
            f"got {calc_company!r}, expected {expected['extracted_company']!r}"
        )

    # 5. Open since formatting (when input is string)
    if isinstance(inp.get("demandReceivedDate"), str):
        calc_open_since = format_open_since(inp["demandReceivedDate"])
        assert calc_open_since == expected["open_since"], (
            f"[{rec_id}] open_since mismatch: "
            f"got {calc_open_since!r}, expected {expected['open_since']!r}"
        )

    # 6. to_requirement_data full object conversion
    req = to_requirement_data(inp)
    dumped = req.model_dump(by_alias=True)
    expected_req = expected["normalized_requirement"]

    # requirementId must follow pattern REQ-YYYY-MM-DD-SEQ
    assert re.match(r"^REQ-\d{4}-\d{2}-\d{2}-\d{3}$", dumped["requirementId"])

    for field_name, expected_val in expected_req.items():
        if field_name == "requirementId":
            continue
        elif field_name == "openSince":
            assert dumped["openSince"] == expected_val, (
                f"[{rec_id}] Field openSince mismatch: "
                f"got {dumped['openSince']!r}, expected {expected_val!r}"
            )
        else:
            assert dumped[field_name] == expected_val, (
                f"[{rec_id}] Field {field_name} mismatch: "
                f"got {dumped[field_name]!r}, expected {expected_val!r}"
            )


def test_normalize_primitives_and_types():
    """Verify JavaScript-to-Python coercion edge cases."""
    assert normalize(None) == NOT_SPECIFIED
    assert normalize("") == NOT_SPECIFIED
    assert normalize("   ") == NOT_SPECIFIED
    assert normalize("n/a") == NOT_SPECIFIED
    assert normalize("N/A") == NOT_SPECIFIED
    assert normalize("-") == NOT_SPECIFIED

    # JS boolean parity: String(true) -> "true", String(false) -> "false"
    assert normalize(True) == "true"
    assert normalize(False) == "false"

    # Numeric types
    assert normalize(42) == "42"
    assert normalize(1500000) == "1500000"
    assert normalize(3.14) == "3.14"

    # Mixed-type arrays: [null, 42, "React"]
    assert normalize(["A", "B"]) == "A, B"
    assert normalize([None, 42, "React"]) == "null, 42, React"

    # Unknown objects / dictionaries
    assert normalize({"key": "val"}) == '{"key": "val"}'


def test_normalize_js_whitespace_trimming():
    """Verify JS whitespace characters (BOM, NBSP, Zs, line terminators) vs non-trimmed ASCII control chars."""
    # Unicode whitespace characters trimmed
    assert normalize("\u00a0\ufeff Senior Engineer \u3000\u2028") == "Senior Engineer"
    # ASCII control characters \x1c-\x1f are NOT trimmed in JS
    assert normalize("\x1cSenior Engineer\x1f") == "\x1cSenior Engineer\x1f"


def test_normalize_skills_delimiters_and_cleaning():
    """Verify skill cleaning, delimiter splitting, and mixed-type filtering."""
    assert normalize_skills("") == []
    assert normalize_skills(None) == []

    # Mixed delimiters: comma, semicolon, pipe
    assert normalize_skills("Java, Python; Go | Rust") == [
        "Java",
        "Python",
        "Go",
        "Rust",
    ]

    # Bullet point stripping
    assert normalize_skills(["- Python", "• React", "* Node.js"]) == [
        "Python",
        "React",
        "Node.js",
    ]

    # Mixed-type array containing nulls, numbers, whitespace, empty strings
    # Matching norm-10: null and empty strings are filtered out, 123 is coerced to "123"
    assert normalize_skills(["AWS", None, 123, "  Terraform  ", ""]) == [
        "AWS",
        "123",
        "Terraform",
    ]

    # Case-insensitive deduplication preserving first casing
    assert normalize_skills(["Python", "python", "PYTHON", "PyThOn"]) == ["Python"]


def test_headcount_formats():
    """Verify headcount preservation for numbers, ranges, and 'Multiple'."""
    assert normalize(5) == "5"
    assert normalize("2-3 openings") == "2-3 openings"
    assert normalize("Multiple") == "Multiple"


def test_extra_unknown_keys_handling():
    """Verify to_requirement_data ignores unexpected LLM hallucinated keys."""
    raw = {
        "jobTitle": "Lead Architect",
        "unexpected_field": "some hallucination",
        "confidence": 0.99,
    }
    req = to_requirement_data(raw)
    dumped = req.model_dump(by_alias=True)
    assert dumped["jobTitle"] == "Lead Architect"
    assert "unexpected_field" not in dumped
    assert "confidence" not in dumped


def test_generic_job_title_resolution():
    """Verify generic title detection and fallback resolution."""
    assert is_generic_job_title("") is True
    assert is_generic_job_title("Not specified") is True
    assert is_generic_job_title("Single Requirement") is True
    assert is_generic_job_title("Requirement 1") is True
    assert is_generic_job_title("Position") is True
    assert is_generic_job_title("Senior Python Developer") is False

    assert resolve_job_title("Requirement 1", "Lead Data Engineer") == "Lead Data Engineer"
    assert resolve_job_title("Requirement 1", "Single Requirement") == NOT_SPECIFIED
    assert resolve_job_title("Staff Engineer", "Hint Title") == "Staff Engineer"


def test_format_open_since():
    """Verify open-since calculation and fallback."""
    assert format_open_since(NOT_SPECIFIED) == NOT_SPECIFIED
    assert format_open_since("invalid-date") == "invalid-date"


def test_split_skill_list():
    """Verify raw skill string split."""
    assert split_skill_list("Python, AWS; Docker | Kubernetes") == [
        "Python",
        "AWS",
        "Docker",
        "Kubernetes",
    ]


def test_extract_job_description_section():
    """Verify JD overview regex extraction."""
    raw = "Header info\nJob Description:\nBuild high-performance microservices."
    assert extract_job_description_section(raw) == "Build high-performance microservices."

    raw_no_match = "Just a short note without section headers."
    assert extract_job_description_section(raw_no_match) == NOT_SPECIFIED


def test_merge_inherited_fields():
    """Verify parent-child inheritance for multi-requirement chunks."""
    parent = {
        "clientLeadPocFrom": "lead@client.com",
        "workMode": "Remote",
        "location": "Bangalore",
        "mandatorySkills": ["AWS"],
    }
    child = {
        "clientLeadPocFrom": NOT_SPECIFIED,
        "workMode": "Hybrid",
        "location": NOT_SPECIFIED,
        "mandatorySkills": ["Python"],
    }
    merged = merge_inherited_fields(child, parent)
    dumped = merged.model_dump(by_alias=True)
    assert dumped["clientLeadPocFrom"] == "lead@client.com"
    assert dumped["workMode"] == "Hybrid"
    assert dumped["location"] == "Bangalore"
    assert dumped["mandatorySkills"] == ["Python"]


def test_clock_determinism_under_shift():
    """Verify clock determinism: pinned by default, shifts accurately, and restores cleanly."""
    from datetime import datetime, timezone

    from app.core import clock

    # 1. Pinned default instant: 2026-10-30T12:00:00Z -> 15 days since 2026-10-15
    assert format_open_since("2026-10-15") == "2026-10-15 (15 days)"
    assert clock.now() == datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)

    # 2. Shift clock by +40 days to 2026-12-09T12:00:00Z -> 55 days since 2026-10-15
    shifted = datetime(2026, 12, 9, 12, 0, 0, tzinfo=timezone.utc)
    clock.set_clock(shifted)
    try:
        assert clock.now() == shifted
        assert format_open_since("2026-10-15") == "2026-10-15 (55 days)"
    finally:
        # 3. Cleanly reset to test instant
        from tests.conftest import TEST_FROZEN_INSTANT

        clock.set_clock(TEST_FROZEN_INSTANT)

    assert format_open_since("2026-10-15") == "2026-10-15 (15 days)"
    assert clock.now() == datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.unpinned_clock
def test_real_clock_without_test_fixture():
    """Prove that without the test fixture, clock.now() is within 2 seconds of real UTC."""
    from datetime import datetime, timezone

    from app.core import clock

    before = datetime.now(timezone.utc)
    val = clock.now()
    after = datetime.now(timezone.utc)
    assert abs((val - before).total_seconds()) < 2.0
    assert abs((after - val).total_seconds()) < 2.0


TIMEZONE_MATRIX_PATH = FIXTURES_DIR / "timezone_matrix.json"


def load_timezone_fixtures():
    with open(TIMEZONE_MATRIX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


TIMEZONE_FIXTURES = load_timezone_fixtures()


@pytest.mark.parametrize("tz_entry", TIMEZONE_FIXTURES, ids=lambda e: e["timezone"])
def test_timezone_date_parity_across_timezones(tz_entry: Dict[str, Any]):
    """Parametrized test running Python under each APP_TIMEZONE against matching Node.js output.

    Verifies:
    1. clock.local_now() and generate_requirement_id() date prefix.
    2. Date.parse epoch milliseconds for ISO date-only (UTC), ISO date-time (local), and legacy formats.
    3. format_open_since() exact string parity with Node.js output.
    """
    from datetime import datetime

    from app.core import clock
    from app.core.normalize import (
        format_open_since,
        generate_requirement_id,
        parse_date_js,
    )

    tz_name = tz_entry["timezone"]
    frozen_dt = datetime.fromisoformat(tz_entry["frozen_instant"].replace("Z", "+00:00"))

    clock.set_clock(frozen_dt)
    clock.set_app_timezone(tz_name)
    try:
        # 1. Requirement ID date prefix matches local date
        req_id = generate_requirement_id()
        assert req_id.startswith(tz_entry["requirement_id_prefix"]), (
            f"[{tz_name}] req_id prefix mismatch: got {req_id}, expected {tz_entry['requirement_id_prefix']}"
        )

        # 2. Date parsing and format_open_since for each format
        for fmt_case in tz_entry["formats"]:
            demand_date = fmt_case["demand_date"]
            exp_ms = fmt_case["parsed_epoch_ms"]
            exp_open_since = fmt_case["open_since"]

            calc_ms = parse_date_js(demand_date)
            assert calc_ms == exp_ms, (
                f"[{tz_name}][{demand_date}] Epoch ms mismatch: got {calc_ms}, expected {exp_ms}"
            )

            calc_open_since = format_open_since(demand_date)
            assert calc_open_since == exp_open_since, (
                f"[{tz_name}][{demand_date}] openSince mismatch: got {calc_open_since!r}, expected {exp_open_since!r}"
            )
    finally:
        from tests.conftest import TEST_FROZEN_INSTANT

        clock.set_clock(TEST_FROZEN_INSTANT)
        clock.reset_app_timezone()
