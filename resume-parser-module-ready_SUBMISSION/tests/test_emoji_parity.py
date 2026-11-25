"""
tests/test_emoji_parity.py
Parity test suite verifying 100% Gate 2 (16-key) equivalence on emoji-injected resumes.
Verifies that non-BMP Unicode characters (e.g. U+1F539 blue diamond, U+1F4E7 email icon)
yield identical parsing results across Python and Node.js at:
- Line start
- Mid-line
- Line end
- Inside the skills section (verifying the TS quirk: emoji admitted as a skill)
- In the resume header
"""
import os
import json
import pytest
from src.parseCoreResumeFields import parse_core_fields_from_resume_text
from src.metaforgeParser import map_legacy_result, apply_evidence_lock
from tests.parity_paths import get_private_parity_dir

PRIV_PARITY = get_private_parity_dir()
GOLDEN_PATH = os.path.join(PRIV_PARITY, "golden", "emoji_node_goldens.json")
CASES_PATH = os.path.join(PRIV_PARITY, "golden", "emoji_cases.json")
BOUNDARY_GOLDEN_PATH = os.path.join(PRIV_PARITY, "golden", "emoji_boundary_goldens.json")
BOUNDARY_CASES_PATH = os.path.join(PRIV_PARITY, "golden", "emoji_boundary_cases.json")

@pytest.mark.skipif(
    not os.path.exists(GOLDEN_PATH) or not os.path.exists(CASES_PATH),
    reason="Emoji golden test cases not found in tests/parity/golden/"
)
def test_emoji_differential_600_cases_parity():
    """Verify 100% equivalence on all 600 emoji-injected test cases against Node.js goldens."""
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        node_goldens = json.load(f)

    keys = [
        'candidateName', 'email', 'contactNumber', 'linkedinUrl', 'highestQualification',
        'skillsRaw', 'technologiesRaw', 'technologies', 'totalExperience', 'relevantExperience',
        'currentEmployer', 'currentLocation', 'location', 'sourceFile', 'parser', 'role'
    ]

    mismatches = []
    for case_id, text in test_cases.items():
        n_obj = node_goldens.get(case_id)
        assert n_obj is not None, f"Missing Node golden for {case_id}"

        parsed = parse_core_fields_from_resume_text(text)
        mapped = map_legacy_result(parsed, "test.txt")
        locked = apply_evidence_lock(mapped, text)

        for k in keys:
            if locked.get(k) != n_obj.get(k):
                mismatches.append((case_id, k, n_obj.get(k), locked.get(k)))

    assert len(mismatches) == 0, f"Found {len(mismatches)} mismatches across 600 emoji test cases: {mismatches[:5]}"


@pytest.mark.skipif(
    not os.path.exists(BOUNDARY_GOLDEN_PATH) or not os.path.exists(BOUNDARY_CASES_PATH),
    reason="Emoji boundary golden test cases not found in tests/parity/golden/"
)
def test_emoji_boundary_234_cases_parity():
    """Verify 100% equivalence on all 234 boundary test cases (limit-1, limit, limit+1 across all length bounds)."""
    with open(BOUNDARY_CASES_PATH, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    with open(BOUNDARY_GOLDEN_PATH, "r", encoding="utf-8") as f:
        node_goldens = json.load(f)

    keys = [
        'candidateName', 'email', 'contactNumber', 'linkedinUrl', 'highestQualification',
        'skillsRaw', 'technologiesRaw', 'technologies', 'totalExperience', 'relevantExperience',
        'currentEmployer', 'currentLocation', 'location', 'sourceFile', 'parser', 'role'
    ]

    mismatches = []
    for case_id, text in test_cases.items():
        n_obj = node_goldens.get(case_id)
        assert n_obj is not None, f"Missing Node golden for {case_id}"

        parsed = parse_core_fields_from_resume_text(text)
        mapped = map_legacy_result(parsed, "test.txt")
        locked = apply_evidence_lock(mapped, text)

        for k in keys:
            if locked.get(k) != n_obj.get(k):
                mismatches.append((case_id, k, n_obj.get(k), locked.get(k)))

    assert len(mismatches) == 0, f"Found {len(mismatches)} mismatches across 234 boundary cases: {mismatches[:5]}"


def test_ts_emoji_quirk_admitted_as_skill():
    """Verify TypeScript quirk where a non-BMP emoji (U+1F539 or U+1F4E7) with UTF-16 length 2
    is admitted into skillsRaw when listed inside the skills section.
    """
    resume_text = (
        "John Doe\njohn.doe@example.com\n+1 555-123-4567\n\n"
        "Technical Skills:\n"
        "🔹, Python, Docker, Kubernetes\n"
    )
    parsed = parse_core_fields_from_resume_text(resume_text)
    mapped = map_legacy_result(parsed, "sample.txt")
    locked = apply_evidence_lock(mapped, resume_text)

    # Emoji '🔹' must be admitted into skillsRaw mirroring Node TypeScript
    assert locked["skillsRaw"] is not None
    assert "🔹" in locked["skillsRaw"]
    assert "Python" in locked["skillsRaw"]

