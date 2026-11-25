import json
import os
import pytest
from src.coreTechKeywords import CORE_TECH_KEYWORDS

def test_core_tech_keywords_parity():
    from tests.parity_paths import get_public_parity_dir
    golden_path = os.path.join(get_public_parity_dir(), 'coreTechKeywords_golden.json')
    with open(golden_path, 'r', encoding='utf-8') as f:
        expected = json.load(f)
    
    assert list(CORE_TECH_KEYWORDS) == expected
    assert len(CORE_TECH_KEYWORDS) == 481

