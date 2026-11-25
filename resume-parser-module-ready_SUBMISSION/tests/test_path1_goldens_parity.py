import os
import json
import pytest
from src.parseCoreResumeFields import parseCoreFieldsFromResumeText
from src.clock import freeze_time
from tests.parity_paths import get_public_parity_dir


def test_path1_goldens_100_percent_parity():
    pub_parity = get_public_parity_dir()
    inputs_dir = os.path.join(pub_parity, 'inputs')
    goldens_dir = os.path.join(pub_parity, 'golden', 'path1_parseCoreFieldsFromResumeText')

    if not os.path.exists(goldens_dir):
        pytest.skip("path1 goldens not found")

    golden_files = [f for f in os.listdir(goldens_dir) if f.endswith('.json')]
    assert len(golden_files) == 143, f"Expected 143 golden files, got {len(golden_files)}"

    mismatches = []
    total_checked = 0

    for gfile in sorted(golden_files):
        input_id = os.path.splitext(gfile)[0]
        input_path = os.path.join(inputs_dir, f"{input_id}.txt")
        golden_path = os.path.join(goldens_dir, gfile)

        if not os.path.exists(input_path):
            mismatches.append(f"Input file missing: {input_path}")
            continue

        with open(input_path, 'r', encoding='utf-8', newline='') as f:
            raw_text = f.read()

        with open(golden_path, 'r', encoding='utf-8') as f:
            expected = json.load(f)

        with freeze_time('2026-11-02T12:00:00.000Z'):
            actual = parseCoreFieldsFromResumeText(raw_text)
        total_checked += 1

        if set(actual.keys()) != set(expected.keys()):
            mismatches.append(
                f"[{input_id}] key set mismatch: missing in actual={set(expected.keys()) - set(actual.keys())}, extra in actual={set(actual.keys()) - set(expected.keys())}"
            )
            continue

        for field, exp_val in expected.items():
            act_val = actual[field]
            if act_val != exp_val:
                mismatches.append(
                    f"[{input_id}] field '{field}' mismatch: expected {json.dumps(exp_val)}, got {json.dumps(act_val)}"
                )

    if mismatches:
        pytest.fail(f"{len(mismatches)} mismatches across {total_checked} cases:\n" + "\n".join(mismatches[:30]))

    print(f"\nAll {total_checked} Path 1 test cases matched golden JSON with 100% parity!")

