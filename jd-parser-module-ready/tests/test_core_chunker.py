"""Parity and unit tests for pure-Python chunking and email extraction (app/core/chunker.py).

Validates parity with TypeScript src/lib/requirement-chunks.ts,
src/lib/multi-requirement-detector.ts, and src/lib/jd-utils.ts across all golden fixtures in:
- tests/fixtures/golden/chunker_regex.json (18 records)
- tests/fixtures/golden/chunker_regex_traps.json (15 edge-case trap records)

Asserts:
- exact string equality for extract_email_headers
- exact match for detect_position_focus_variants
- exact match for split_requirements
- exact match for post_process_chunks
- exact match for extract_common_metadata
- exact match for regex_augment
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from app.core.chunker import (
    detect_position_focus_variants,
    extract_common_metadata,
    extract_email_headers,
    infer_title_from_focus,
    is_tiny_position_chunk,
    post_process_chunks,
    regex_augment,
    split_requirements,
    strip_footer,
    utf16_len,
    utf16_slice,
)
from app.schemas.requirement import RequirementData

FIXTURES_DIR = Path("tests/fixtures/golden")


def load_fixture_records(filename: str):
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


CHUNKER_RECORDS = load_fixture_records("chunker_regex.json")
TRAP_RECORDS = load_fixture_records("chunker_regex_traps.json")
TRAP2_RECORDS = load_fixture_records("chunker_regex_traps2.json")


# =========================================================================
# Area 1: chunker_regex.json (18 standard golden records)
# =========================================================================


@pytest.mark.parametrize("record", CHUNKER_RECORDS, ids=lambda r: r["id"])
def test_email_headers_golden_parity(record: Dict[str, Any]):
    """Verify exact header extraction parity with TypeScript extractEmailHeaders."""
    raw_text = record["input"]["raw_text"]
    expected_headers = record["expected_output"]["email_headers"]
    calc_headers = extract_email_headers(raw_text)
    assert calc_headers == expected_headers, f"[{record['id']}] Header mismatch"


@pytest.mark.parametrize("record", CHUNKER_RECORDS, ids=lambda r: r["id"])
def test_position_focus_variants_golden_parity(record: Dict[str, Any]):
    """Verify position focus variant detection parity."""
    raw_text = record["input"]["raw_text"]
    expected_variants = record["expected_output"].get("position_focus_variants") or []
    calc_variants = detect_position_focus_variants(raw_text) or []

    assert len(calc_variants) == len(expected_variants), f"[{record['id']}] Variant count mismatch"
    for i, (calc, exp) in enumerate(zip(calc_variants, expected_variants)):
        assert calc["title"] == exp["title"], f"[{record['id']}][{i}] Title mismatch"
        assert calc["content"] == exp["content"], f"[{record['id']}][{i}] Content mismatch"
        assert calc.get("numberOfPositions") == exp.get("numberOfPositions"), (
            f"[{record['id']}][{i}] Openings mismatch"
        )


@pytest.mark.parametrize("record", CHUNKER_RECORDS, ids=lambda r: r["id"])
def test_split_requirements_golden_parity(record: Dict[str, Any]):
    """Verify multi-requirement splitting parity."""
    raw_text = record["input"]["raw_text"]
    expected_chunks = record["expected_output"]["split_chunks"]
    calc_chunks = split_requirements(raw_text)

    assert len(calc_chunks) == len(expected_chunks), f"[{record['id']}] Chunk count mismatch"
    for i, (calc, exp) in enumerate(zip(calc_chunks, expected_chunks)):
        assert calc["title"] == exp["title"], f"[{record['id']}][{i}] Title mismatch"
        assert calc["content"] == exp["content"], f"[{record['id']}][{i}] Content mismatch"


@pytest.mark.parametrize("record", CHUNKER_RECORDS, ids=lambda r: r["id"])
def test_post_process_chunks_golden_parity(record: Dict[str, Any]):
    """Verify chunk post-processing and email context enrichment parity."""
    raw_text = record["input"]["raw_text"]
    split_chunks = split_requirements(raw_text)
    expected_post_chunks = record["expected_output"]["post_processed_chunks"]

    calc_post_chunks = post_process_chunks(raw_text, split_chunks)

    assert len(calc_post_chunks) == len(expected_post_chunks), (
        f"[{record['id']}] Post chunk count mismatch"
    )
    for i, (calc, exp) in enumerate(zip(calc_post_chunks, expected_post_chunks)):
        assert calc["title"] == exp["title"], f"[{record['id']}][{i}] Post title mismatch"
        assert calc["content"] == exp["content"], f"[{record['id']}][{i}] Post content mismatch"


@pytest.mark.parametrize("record", CHUNKER_RECORDS, ids=lambda r: r["id"])
def test_extract_common_metadata_golden_parity(record: Dict[str, Any]):
    """Verify common metadata extraction parity."""
    raw_text = record["input"]["raw_text"]
    expected_cm = record["expected_output"]["common_metadata"]
    calc_cm = extract_common_metadata(raw_text)
    assert calc_cm == expected_cm, f"[{record['id']}] Common metadata mismatch"


@pytest.mark.parametrize("record", CHUNKER_RECORDS, ids=lambda r: r["id"])
def test_regex_augment_golden_parity(record: Dict[str, Any]):
    """Verify regex heuristic augmentation parity."""
    raw_text = record["input"]["raw_text"]
    expected_aug = record["expected_output"]["regex_augmented"]
    calc_aug = regex_augment(raw_text, RequirementData())

    for k, expected_v in expected_aug.items():
        assert calc_aug.get(k) == expected_v, (
            f"[{record['id']}] Augment mismatch on field '{k}': got {calc_aug.get(k)!r}, expected {expected_v!r}"
        )


# =========================================================================
# Area 2: chunker_regex_traps.json (15 edge-case trap records)
# =========================================================================


@pytest.mark.parametrize("record", TRAP_RECORDS, ids=lambda r: r["id"])
def test_email_headers_traps_parity(record: Dict[str, Any]):
    """Verify exact header extraction parity on edge-case trap inputs."""
    raw_text = record["input"]["raw_text"]
    expected_headers = record["expected_output"]["email_headers"]
    calc_headers = extract_email_headers(raw_text)
    assert calc_headers == expected_headers, f"[{record['id']}] Trap header mismatch"


@pytest.mark.parametrize("record", TRAP_RECORDS, ids=lambda r: r["id"])
def test_position_focus_variants_traps_parity(record: Dict[str, Any]):
    """Verify position focus variant detection parity on edge-case trap inputs."""
    raw_text = record["input"]["raw_text"]
    expected_variants = record["expected_output"].get("position_focus_variants") or []
    calc_variants = detect_position_focus_variants(raw_text) or []

    assert len(calc_variants) == len(expected_variants), (
        f"[{record['id']}] Trap variant count mismatch"
    )
    for i, (calc, exp) in enumerate(zip(calc_variants, expected_variants)):
        assert calc["title"] == exp["title"], f"[{record['id']}][{i}] Trap title mismatch"
        assert calc["content"] == exp["content"], f"[{record['id']}][{i}] Trap content mismatch"
        assert calc.get("numberOfPositions") == exp.get("numberOfPositions"), (
            f"[{record['id']}][{i}] Trap openings mismatch"
        )


@pytest.mark.parametrize("record", TRAP_RECORDS, ids=lambda r: r["id"])
def test_split_requirements_traps_parity(record: Dict[str, Any]):
    """Verify multi-requirement splitting parity on edge-case trap inputs."""
    raw_text = record["input"]["raw_text"]
    expected_chunks = record["expected_output"]["split_chunks"]
    calc_chunks = split_requirements(raw_text)

    assert len(calc_chunks) == len(expected_chunks), f"[{record['id']}] Trap split count mismatch"
    for i, (calc, exp) in enumerate(zip(calc_chunks, expected_chunks)):
        assert calc["title"] == exp["title"], f"[{record['id']}][{i}] Trap split title mismatch"
        assert calc["content"] == exp["content"], (
            f"[{record['id']}][{i}] Trap split content mismatch"
        )


@pytest.mark.parametrize("record", TRAP_RECORDS, ids=lambda r: r["id"])
def test_post_process_chunks_traps_parity(record: Dict[str, Any]):
    """Verify chunk post-processing and email context enrichment on edge-case trap inputs."""
    raw_text = record["input"]["raw_text"]
    split_chunks = split_requirements(raw_text)
    expected_post_chunks = record["expected_output"]["post_processed_chunks"]

    calc_post_chunks = post_process_chunks(raw_text, split_chunks)

    assert len(calc_post_chunks) == len(expected_post_chunks), (
        f"[{record['id']}] Trap post chunk count mismatch"
    )
    for i, (calc, exp) in enumerate(zip(calc_post_chunks, expected_post_chunks)):
        assert calc["title"] == exp["title"], f"[{record['id']}][{i}] Trap post title mismatch"
        assert calc["content"] == exp["content"], (
            f"[{record['id']}][{i}] Trap post content mismatch"
        )


@pytest.mark.parametrize("record", TRAP_RECORDS, ids=lambda r: r["id"])
def test_extract_common_metadata_traps_parity(record: Dict[str, Any]):
    """Verify common metadata extraction on edge-case trap inputs."""
    raw_text = record["input"]["raw_text"]
    expected_cm = record["expected_output"]["common_metadata"]
    calc_cm = extract_common_metadata(raw_text)
    assert calc_cm == expected_cm, f"[{record['id']}] Trap common metadata mismatch"


@pytest.mark.parametrize("record", TRAP_RECORDS, ids=lambda r: r["id"])
def test_regex_augment_traps_parity(record: Dict[str, Any]):
    """Verify regex heuristic augmentation on edge-case trap inputs."""
    raw_text = record["input"]["raw_text"]
    expected_aug = record["expected_output"]["regex_augmented"]
    calc_aug = regex_augment(raw_text, RequirementData())

    for k, expected_v in expected_aug.items():
        assert calc_aug.get(k) == expected_v, (
            f"[{record['id']}] Trap augment mismatch on field '{k}': got {calc_aug.get(k)!r}, expected {expected_v!r}"
        )


# =========================================================================
# Area 3: chunker_regex_traps2.json (12 targeted regex edge-case trap records)
# =========================================================================


@pytest.mark.parametrize("record", TRAP2_RECORDS, ids=lambda r: r["id"])
def test_email_headers_traps2_parity(record: Dict[str, Any]):
    """Verify exact header extraction parity on targeted trap 2 inputs."""
    raw_text = record["input"]["raw_text"]
    expected_headers = record["expected_output"]["email_headers"]
    calc_headers = extract_email_headers(raw_text)
    assert calc_headers == expected_headers, f"[{record['id']}] Trap 2 header mismatch"


@pytest.mark.parametrize("record", TRAP2_RECORDS, ids=lambda r: r["id"])
def test_position_focus_variants_traps2_parity(record: Dict[str, Any]):
    """Verify position focus variant detection parity on targeted trap 2 inputs."""
    raw_text = record["input"]["raw_text"]
    expected_variants = record["expected_output"].get("position_focus_variants") or []
    calc_variants = detect_position_focus_variants(raw_text) or []

    assert len(calc_variants) == len(expected_variants), (
        f"[{record['id']}] Trap 2 variant count mismatch"
    )
    for i, (calc, exp) in enumerate(zip(calc_variants, expected_variants)):
        assert calc["title"] == exp["title"], f"[{record['id']}][{i}] Trap 2 title mismatch"
        assert calc["content"] == exp["content"], f"[{record['id']}][{i}] Trap 2 content mismatch"
        assert calc.get("numberOfPositions") == exp.get("numberOfPositions"), (
            f"[{record['id']}][{i}] Trap 2 openings mismatch"
        )


@pytest.mark.parametrize("record", TRAP2_RECORDS, ids=lambda r: r["id"])
def test_split_requirements_traps2_parity(record: Dict[str, Any]):
    """Verify multi-requirement splitting parity on targeted trap 2 inputs."""
    raw_text = record["input"]["raw_text"]
    expected_chunks = record["expected_output"]["split_chunks"]
    calc_chunks = split_requirements(raw_text)

    assert len(calc_chunks) == len(expected_chunks), f"[{record['id']}] Trap 2 split count mismatch"
    for i, (calc, exp) in enumerate(zip(calc_chunks, expected_chunks)):
        assert calc["title"] == exp["title"], f"[{record['id']}][{i}] Trap 2 split title mismatch"
        assert calc["content"] == exp["content"], (
            f"[{record['id']}][{i}] Trap 2 split content mismatch"
        )


@pytest.mark.parametrize("record", TRAP2_RECORDS, ids=lambda r: r["id"])
def test_post_process_chunks_traps2_parity(record: Dict[str, Any]):
    """Verify chunk post-processing and email context enrichment on targeted trap 2 inputs."""
    raw_text = record["input"]["raw_text"]
    split_chunks = split_requirements(raw_text)
    expected_post_chunks = record["expected_output"]["post_processed_chunks"]

    calc_post_chunks = post_process_chunks(raw_text, split_chunks)

    assert len(calc_post_chunks) == len(expected_post_chunks), (
        f"[{record['id']}] Trap 2 post chunk count mismatch"
    )
    for i, (calc, exp) in enumerate(zip(calc_post_chunks, expected_post_chunks)):
        assert calc["title"] == exp["title"], f"[{record['id']}][{i}] Trap 2 post title mismatch"
        assert calc["content"] == exp["content"], (
            f"[{record['id']}][{i}] Trap 2 post content mismatch"
        )


@pytest.mark.parametrize("record", TRAP2_RECORDS, ids=lambda r: r["id"])
def test_extract_common_metadata_traps2_parity(record: Dict[str, Any]):
    """Verify common metadata extraction on targeted trap 2 inputs."""
    raw_text = record["input"]["raw_text"]
    expected_cm = record["expected_output"]["common_metadata"]
    calc_cm = extract_common_metadata(raw_text)
    assert calc_cm == expected_cm, f"[{record['id']}] Trap 2 common metadata mismatch"


@pytest.mark.parametrize("record", TRAP2_RECORDS, ids=lambda r: r["id"])
def test_regex_augment_traps2_parity(record: Dict[str, Any]):
    """Verify regex heuristic augmentation on targeted trap 2 inputs."""
    raw_text = record["input"]["raw_text"]
    expected_aug = record["expected_output"]["regex_augmented"]
    calc_aug = regex_augment(raw_text, RequirementData())

    for k, expected_v in expected_aug.items():
        assert calc_aug.get(k) == expected_v, (
            f"[{record['id']}] Trap 2 augment mismatch on field '{k}': got {calc_aug.get(k)!r}, expected {expected_v!r}"
        )


# =========================================================================
# Helper and boundary unit tests
# =========================================================================


def test_strip_footer_variations():
    """Verify email footer and disclaimer stripping."""
    text1 = "Job description\nRegards,\nJohn Doe"
    assert strip_footer(text1) == "Job description"

    text2 = "Job description\nDisclaimer: confidential\nDetails"
    assert strip_footer(text2) == "Job description"

    text3 = "Job description with no footer."
    assert strip_footer(text3) == "Job description with no footer."

    text4 = "Job description\r\nRegards,\r\nJane Doe"
    assert strip_footer(text4) == "Job description"


def test_is_tiny_position_chunk():
    """Verify tiny position chunk identification."""
    tiny = {"title": "Pos 1", "content": "Position 1 to be focused on Java"}
    assert is_tiny_position_chunk(tiny) is True

    large = {"title": "Pos 1", "content": "Position 1 " + "x" * 600}
    assert is_tiny_position_chunk(large) is False

    non_position = {"title": "General", "content": "Looking for a developer"}
    assert is_tiny_position_chunk(non_position) is False


def test_infer_title_from_focus_specialized():
    """Verify SAP FI and CO focus title inferences."""
    t_fi = infer_title_from_focus("1", "FI Banking and FSCM experience", "Subject: Role")
    assert t_fi == "SAP FI Consultant (Banking & FSCM)"

    t_co = infer_title_from_focus("2", "Product Costing and CO-PA", "Subject: Role")
    assert t_co == "SAP CO Consultant (Product Costing & CO-PA)"

    t_generic = infer_title_from_focus(
        "3", "React Developer", "Subject: Full Stack Dev @ Bangalore"
    )
    assert t_generic == "Full Stack Dev — Position 3"


def test_utf16_helpers():
    """Verify UTF-16 code unit length and slicing matching JS semantics."""
    s = "Hello 🚀 World!"  # 🚀 is 1 code point, 2 UTF-16 code units
    assert len(s) == 14  # Python len (code points)
    assert utf16_len(s) == 15  # JS .length (UTF-16 code units)

    # Slice around emoji
    assert utf16_slice(s, 0, 5) == "Hello"
    assert utf16_slice(s, 6, 8) == "🚀"
    assert utf16_slice(s, 9, 15) == "World!"
