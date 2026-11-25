"""Parity and unit tests for pure-Python reward logic (app/core/reward.py).

Validates exact parity with TypeScript src/lib/reward.ts across all golden fixtures in:
- tests/fixtures/golden/reward.json (18 records)

Asserts:
- exact boolean equality for below-0.98 meaningful diff decision
- pytest.approx(abs=1e-9) for composite reward_score
- pytest.approx(abs=1e-9) for each individual field score in field_rewards
- snake_case keys only {"score": float, "field_rewards": Dict[str, float]}
- JS whitespace trimming/collapsing behavior
- js_string coercion parity
- dynamic TOTAL_WEIGHT calculation from FIELD_WEIGHTS
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from app.core.reward import (
    FIELD_WEIGHTS,
    TOTAL_WEIGHT,
    compute_reward,
    has_meaningful_diff,
    js_collapse_whitespace,
    js_json_stringify,
    js_string,
    js_trim,
    normalize_string,
    score_skills,
    score_string,
)

FIXTURES_PATH = Path("tests/fixtures/golden/reward.json")
BOUNDARY_FIXTURES_PATH = Path("tests/fixtures/golden/reward_boundary.json")


def load_reward_records():
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_reward_boundary_records():
    with open(BOUNDARY_FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


REWARD_RECORDS = load_reward_records()
BOUNDARY_RECORDS = load_reward_boundary_records()


@pytest.mark.parametrize("record", REWARD_RECORDS, ids=lambda r: r["id"])
def test_reward_golden_parity(record: Dict[str, Any]):
    """Parametrized test for each record in tests/fixtures/golden/reward.json."""
    pred = record["input"]["predicted"]
    corr = record["input"]["corrected"]
    expected_score = record["expected_output"]["reward_score"]
    expected_diff = record["expected_output"]["has_meaningful_diff"]
    expected_fields = record["expected_output"]["field_rewards"]

    calc_result = compute_reward(pred, corr)

    # 1. Returned dictionary has strictly snake_case keys (no duplicate camelCase "fieldRewards")
    assert set(calc_result.keys()) == {"score", "field_rewards"}

    calc_score = calc_result["score"]
    calc_fields = calc_result["field_rewards"]
    calc_diff = has_meaningful_diff(pred, corr)

    # 2. Below-0.98 decision matches for every record
    assert calc_diff == expected_diff, (
        f"[{record['id']}] Meaningful diff (< 0.98) decision mismatch: "
        f"got {calc_diff}, expected {expected_diff}"
    )

    # 3. Composite reward score matches with pytest.approx(abs=1e-9)
    assert calc_score == pytest.approx(expected_score, abs=1e-9), (
        f"[{record['id']}] Composite reward_score mismatch: "
        f"got {calc_score}, expected {expected_score}"
    )

    # 4. Composite score is strictly clamped to [0.0, 1.0]
    assert 0.0 <= calc_score <= 1.0, f"[{record['id']}] Score {calc_score} out of [0, 1] range"

    # 5. Per-field reward scores match with pytest.approx(abs=1e-9)
    for field_name, exp_field_score in expected_fields.items():
        assert field_name in calc_fields, (
            f"[{record['id']}] Missing field {field_name} in field_rewards"
        )
        assert calc_fields[field_name] == pytest.approx(exp_field_score, abs=1e-9), (
            f"[{record['id']}] Field {field_name} score mismatch: "
            f"got {calc_fields[field_name]}, expected {exp_field_score}"
        )


@pytest.mark.parametrize("record", BOUNDARY_RECORDS, ids=lambda r: r["id"])
def test_reward_boundary_golden_parity(record: Dict[str, Any]):
    """Parametrized test for 8 boundary pairs within 0.001 of 0.98 in reward_boundary.json."""
    pred = record["input"]["predicted"]
    corr = record["input"]["corrected"]
    expected_score = record["expected_output"]["reward_score"]
    expected_diff = record["expected_output"]["has_meaningful_diff"]
    expected_fields = record["expected_output"]["field_rewards"]

    calc_result = compute_reward(pred, corr)
    calc_score = calc_result["score"]
    calc_fields = calc_result["field_rewards"]
    calc_diff = has_meaningful_diff(pred, corr)

    # 1. Below-0.98 decision (< 0.98) matches exactly
    assert calc_diff == expected_diff, (
        f"[{record['id']}] Meaningful diff (< 0.98) decision mismatch: "
        f"got {calc_diff}, expected {expected_diff}"
    )

    # 2. Composite reward score matches with pytest.approx(abs=1e-9)
    assert calc_score == pytest.approx(expected_score, abs=1e-9), (
        f"[{record['id']}] Composite reward_score mismatch: "
        f"got {calc_score}, expected {expected_score}"
    )

    # 3. Composite score is strictly clamped to [0.0, 1.0]
    assert 0.0 <= calc_score <= 1.0, f"[{record['id']}] Score {calc_score} out of [0, 1] range"

    # 4. Per-field reward scores match with pytest.approx(abs=1e-9)
    for field_name, exp_field_score in expected_fields.items():
        assert field_name in calc_fields, (
            f"[{record['id']}] Missing field {field_name} in field_rewards"
        )
        assert calc_fields[field_name] == pytest.approx(exp_field_score, abs=1e-9), (
            f"[{record['id']}] Field {field_name} score mismatch: "
            f"got {calc_fields[field_name]}, expected {exp_field_score}"
        )


def test_total_weight_matches_sum():
    """Verify total weight is dynamically computed from weights table (no hard-coded value)."""
    expected_sum = sum(FIELD_WEIGHTS.values())
    assert pytest.approx(TOTAL_WEIGHT, abs=1e-9) == expected_sum
    assert pytest.approx(TOTAL_WEIGHT, abs=1e-9) == 24.0


def test_js_string_helper():
    """Verify js_string helper matches JavaScript String() coercion rules."""
    assert js_string(None) == "null"
    assert js_string(True) == "true"
    assert js_string(False) == "false"
    assert js_string(42) == "42"
    assert js_string(1.0) == "1"
    assert js_string(1.5) == "1.5"
    assert js_string("already a string") == "already a string"
    assert js_string([]) == ""
    assert js_string([1, 2, 3]) == "1,2,3"
    assert js_string([None, 42, "React"]) == ",42,React"


def test_js_whitespace_and_trim():
    """Verify JS whitespace characters (Zs category, BOM, line terminators) vs non-trimmed ASCII control chars."""
    # Characters that JS trims: \u00a0 (NBSP), \ufeff (BOM), \u2028 (LS), \u2029 (PS), \u3000 (ideographic space)
    raw_js_ws = "\u00a0\ufeff\u2028\u2029\u3000   Senior Developer   \u3000\u2028\ufeff\u00a0"
    assert js_trim(raw_js_ws) == "Senior Developer"

    # ASCII control characters \x1c-\x1f are NOT whitespace in JS and must NOT be trimmed
    raw_ascii_ctrl = "\x1cSenior Developer\x1f"
    assert js_trim(raw_ascii_ctrl) == "\x1cSenior Developer\x1f"

    # Whitespace collapsing handles internal Unicode whitespace
    raw_internal = "Senior\u00a0\u3000\u2028Developer"
    assert js_collapse_whitespace(raw_internal) == "Senior Developer"

    # Full normalize_string pipeline with mixed whitespace
    assert (
        normalize_string("\u00a0\ufeff Senior\u3000Software\u2028Engineer \ufeff")
        == "senior software engineer"
    )
    assert normalize_string("\x1cPython\x1f") == "\x1cpython\x1f"


def test_score_string_edge_cases():
    """Verify score_string rules for exact, overlap, and not-specified."""
    assert score_string("", "") == 1.0
    assert score_string("Not specified", "Not specified") == 1.0
    assert score_string("Not specified", "Python Dev") == 0.0
    assert score_string("Python Dev", "Not specified") == 0.0
    assert score_string("Senior Engineer", "senior engineer") == 1.0
    assert score_string("Engineer", "Senior Engineer") == 0.8
    assert score_string("Lead Architect", "Junior") == 0.0


def test_score_skills_edge_cases():
    """Verify score_skills F1 calculation and zero-division handling."""
    assert score_skills([], []) == 1.0
    assert score_skills(["Python"], []) == 0.0
    assert score_skills([], ["Python"]) == 0.0
    # Duplicate and case-different skill tags collapse to same set item
    assert score_skills(["Python", "python", "PYTHON"], ["python"]) == 1.0
    # Disjoint
    assert score_skills(["Go"], ["Rust"]) == 0.0


JS_NUM_PATH = Path("tests/fixtures/golden/js_number_to_string.json")


def load_js_number_records():
    if JS_NUM_PATH.exists():
        with open(JS_NUM_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


JS_NUMBER_RECORDS = load_js_number_records()


@pytest.mark.parametrize("record", JS_NUMBER_RECORDS, ids=lambda r: r["id"])
def test_js_number_to_string_golden_parity(record: Dict[str, Any]):
    """Assert Python number parsing and coercion matches ECMAScript String(JSON.parse(text))."""
    import json

    val = json.loads(record["json_text"])
    coerced = js_string(val)
    assert coerced == record["expected"], (
        f"Mismatch on {record['id']} for text {record['json_text']!r}"
    )


JS_JSON_STRINGIFY_PATH = Path("tests/fixtures/golden/js_json_stringify.json")


def load_js_json_stringify_records():
    if JS_JSON_STRINGIFY_PATH.exists():
        with open(JS_JSON_STRINGIFY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


JS_JSON_STRINGIFY_RECORDS = load_js_json_stringify_records()


@pytest.mark.parametrize("record", JS_JSON_STRINGIFY_RECORDS, ids=lambda r: r["id"])
def test_js_json_stringify_golden_parity(record: Dict[str, Any]):
    """Assert Python js_json_stringify matches ECMAScript JSON.stringify byte-for-byte."""

    t = record["type"]
    if t == "number_tagged":
        raw = record["input"]
        if raw == "NaN":
            val = float("nan")
        elif raw == "Infinity":
            val = float("inf")
        elif raw == "-Infinity":
            val = float("-inf")
        elif raw == "-0":
            val = -0.0
        elif raw == "0":
            val = 0.0
        else:
            val = float(raw)
    elif t == "string_code_units":
        val = "".join(chr(c) for c in record["input"])
    elif t == "json_value":
        val = record["input"]
    else:
        raise ValueError(f"Unknown test case type: {t}")

    actual = js_json_stringify(val)
    assert actual == record["expected_output"], (
        f"Mismatch on {record['id']} ({record['description']}): got {actual!r}, expected {record['expected_output']!r}"
    )
