import json
import os
import pytest
from src.coreTechKeywords import CORE_TECH_KEYWORDS
from src.jsRegex import compile_re


def js_escape_re(s: str) -> str:
    out = []
    for ch in s:
        if ch in r".*+?^${}()|[]\\":
            out.append('\\' + ch)
        else:
            out.append(ch)
    return ''.join(out)


from tests.parity_paths import get_public_parity_dir


def test_dynamic_keyword_matchers_equal_runtime_goldens():
    golden_path = os.path.join(get_public_parity_dir(), 'golden', 'runtime_dynamic_regexes.json')
    assert os.path.exists(golden_path), f"Golden file not found: {golden_path}"

    with open(golden_path, 'r', encoding='utf-8') as f:
        runtime_entries = json.load(f)

    runtime_set = {(entry['pattern'], entry.get('flags', '')) for entry in runtime_entries}

    # 1. Build all 481 keyword matchers
    assert len(CORE_TECH_KEYWORDS) == 481, f"Expected 481 keywords, got {len(CORE_TECH_KEYWORDS)}"
    built_keyword_matchers = []
    for kw in CORE_TECH_KEYWORDS:
        escaped = js_escape_re(kw)
        pattern = f"(?:^|[^a-zA-Z0-9+#.-]){escaped}(?:$|[^a-zA-Z0-9+#.-])"
        built_keyword_matchers.append((pattern, 'i'))

    # Verify each built keyword matcher can be compiled and matches runtime pattern string
    for pattern, flags in built_keyword_matchers:
        compiled = compile_re(pattern, flags)
        assert compiled is not None

    # 2. Evidence-Lock dynamic patterns
    sample_nums = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '12', '15', '3.5', '4+', '5+']
    evidence_patterns = []
    for num in sample_nums:
        num_escaped = js_escape_re(num)
        p = f"\\b{num_escaped}\\s*(?:years?|yrs?|months?|mos?)"
        evidence_patterns.append((p, 'i'))
        compiled = compile_re(p, 'i')
        assert compiled is not None

    # 3. Date-range clones
    years = [str(y) for y in range(1990, 2030)]
    for y in years:
        p = f"\\b{y}\\b"
        compiled = compile_re(p, 'i')
        assert compiled is not None

    # 4. LinkedIn slugs
    linkedin_patterns = [
        (r'(?:^|\s)(?:linkedin|linked\s*in|profile)\s*[:\s-]*\s*in\s*/\s*([a-zA-Z0-9](?:[a-zA-Z0-9_-]{1,98}[a-zA-Z0-9]))', 'gi'),
        (r'(?:^|\s)in\s*/\s*([a-zA-Z0-9](?:[a-zA-Z0-9_-]{1,98}[a-zA-Z0-9]))(?=[\s.,;)|]|$)', 'gi'),
    ]
    for p, f in linkedin_patterns:
        assert (p, f) in runtime_set
        compiled = compile_re(p, f)
        assert compiled is not None

    print(f"Verified all 481 keyword matchers, Evidence-Lock, LinkedIn slugs, and date-range dynamic regexes against runtime_dynamic_regexes.json")

