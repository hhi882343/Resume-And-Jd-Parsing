"""
Test Suite for jsRegex.py: Asserts 100% Parity with regex_golden.json
"""
import json
import os
import pytest
from src.jsRegex import compile_re, js_trim, js_round, to_js_utf16_surrogates, from_js_utf16_surrogates


def test_js_round_parity():
    # JavaScript Math.round semantics
    assert js_round(2.5) == 3
    assert js_round(3.5) == 4
    assert js_round(2.4) == 2
    assert js_round(2.6) == 3
    assert js_round(-1.5) == -1
    assert js_round(-1.6) == -2
    assert js_round(0.0) == 0


def test_js_trim_parity():
    assert js_trim("   hello world   ") == "hello world"
    assert js_trim("\u00a0hello\u00a0") == "hello"
    assert js_trim("\ufefftest\ufeff") == "test"
    assert js_trim("\n\r\t  padded  \r\n") == "padded"
    assert js_trim("") == ""
    assert js_trim(None) == ""


from tests.parity_paths import get_public_parity_dir


def test_regex_golden_parity():
    pub_parity = get_public_parity_dir()
    golden_path = os.path.join(pub_parity, 'regex_golden.json')
    inputs_dir = os.path.join(pub_parity, 'inputs')

    if not os.path.exists(golden_path):
        pytest.skip("regex_golden.json not found")

    with open(golden_path, 'r', encoding='utf-8') as f:
        regex_golden = json.load(f)

    # Cache inputs with newline='' to prevent Python universal newlines from mutating CRLF to LF
    inputs_cache = {}
    for fname in os.listdir(inputs_dir):
        if fname.endswith('.txt'):
            input_id = os.path.splitext(fname)[0]
            with open(os.path.join(inputs_dir, fname), 'r', encoding='utf-8', newline='') as f:
                raw_content = f.read()
                # Apply UTF-16 surrogate view to mirror Node V8 code units
                inputs_cache[input_id] = to_js_utf16_surrogates(raw_content)

    total_patterns_tested = 0
    total_matches_verified = 0

    for regex_key, golden_data in regex_golden.items():
        pattern_str = golden_data['pattern']
        flags = golden_data['flags']

        # Handle dynamic template placeholder replacements
        if '${uid}' in pattern_str:
            uid = r'[a-zA-Z0-9][-a-zA-Z0-9_]{1,100}[a-zA-Z0-9]'
            pattern_str = pattern_str.replace('${uid}', uid)
        elif '${numEscaped}' in pattern_str:
            pattern_str = pattern_str.replace('${numEscaped}', r'\d+')
        elif '${escaped}' in pattern_str:
            pattern_str = pattern_str.replace('${escaped}', r'[a-zA-Z0-9+#.-]+')

        try:
            cre = compile_re(pattern_str, flags)
        except Exception as e:
            pytest.fail(f"Failed to compile pattern {regex_key}: {pattern_str} ({e})")

        total_patterns_tested += 1

        for input_id, expected_matches in golden_data['inputs'].items():
            if input_id not in inputs_cache:
                continue

            doc_text = inputs_cache[input_id]
            py_matches = []

            for m in cre.finditer(doc_text):
                py_matches.append({
                    'index': m.start(),
                    'length': m.end() - m.start(),
                    'text': from_js_utf16_surrogates(m.group(0)),
                    'groups': [from_js_utf16_surrogates(g) if g is not None else None for g in m.groups()]
                })

            assert len(py_matches) == len(expected_matches), (
                f"Match count mismatch for {regex_key} on {input_id}: "
                f"expected {len(expected_matches)}, got {len(py_matches)}"
            )

            for exp_m, act_m in zip(expected_matches, py_matches):
                assert act_m['index'] == exp_m['index'], (
                    f"Index mismatch for {regex_key} on {input_id}: expected {exp_m['index']}, got {act_m['index']}"
                )
                assert act_m['length'] == exp_m['length'], (
                    f"Length mismatch for {regex_key} on {input_id}: expected {exp_m['length']}, got {act_m['length']}"
                )
                assert act_m['text'] == exp_m['text'], (
                    f"Text mismatch for {regex_key} on {input_id}: expected {exp_m['text']}, got {act_m['text']}"
                )
                assert act_m['groups'] == exp_m['groups'], (
                    f"Groups mismatch for {regex_key} on {input_id}: expected {exp_m['groups']}, got {act_m['groups']}"
                )
                total_matches_verified += 1

    print(f"\n[PARITY GATE PASSED] Verified {total_patterns_tested} active regex patterns across {total_matches_verified} match instances!")


def test_unmatched_regexes_with_phase2b_fixtures():
    pub_parity = get_public_parity_dir()
    fixtures_path = os.path.join(pub_parity, 'golden', 'unmatched_regex_fixtures.json')
    node_eval_path = os.path.join(pub_parity, 'golden', 'unmatched_node_eval.json')
    if not os.path.exists(fixtures_path) or not os.path.exists(node_eval_path):
        pytest.skip("unmatched regex golden fixtures not found")

    with open(fixtures_path, 'r', encoding='utf-8') as f:
        fixtures = json.load(f)

    with open(node_eval_path, 'r', encoding='utf-8') as f:
        node_evals = {x['catalog_index']: x for x in json.load(f)}

    assert len(fixtures) == 246, f"Expected 246 fixtures, got {len(fixtures)}"

    for f in fixtures:
        idx = f['catalog_index']
        pattern = f['pattern']
        flags = f.get('flags', '')
        if pattern == 'pattern.source':
            pattern = r'(?:email|e-?mail|mail)\s*[:\-]?\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})'
            flags = 'gi'
        elif pattern == 're.source':
            pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
            flags = 'gi'
        elif '`' in pattern or '${' in pattern:
            pattern = pattern.replace('`', '')
            pattern = pattern.replace('${startNames.source}', 'Education')
            pattern = pattern.replace('${endBefore.source}', 'Experience')
            pattern = pattern.replace('${slugPart}', r'[a-zA-Z0-9](?:[a-zA-Z0-9_-]{1,98}[a-zA-Z0-9])')
            pattern = pattern.replace('${prefix}', r'\b')
            pattern = pattern.replace('${suffix}', r'\b')
            pattern = pattern.replace('${escaped}', r'[a-zA-Z0-9+#.-]+')

        cre = compile_re(pattern, flags)
        node_res = node_evals[idx]

        # Positive string
        pos_m = cre.search(f['positive_test_string'])
        if node_res['pos'] is None:
            assert pos_m is None
        else:
            assert pos_m is not None
            assert pos_m.start() == node_res['pos']['index']
            assert pos_m.group(0) == node_res['pos']['text']

        # Negative string
        neg_m = cre.search(f['negative_test_string'])
        if node_res['neg'] is None:
            assert neg_m is None
        else:
            assert neg_m is not None
            assert neg_m.start() == node_res['neg']['index']
            assert neg_m.group(0) == node_res['neg']['text']

    print(f"\n[PARITY GATE PASSED] Verified all 246 unmatched regex fixtures with 100% parity against Node!")


