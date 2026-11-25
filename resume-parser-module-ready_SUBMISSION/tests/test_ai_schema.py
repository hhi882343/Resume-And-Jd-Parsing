import pytest
from src.ai.schema import validateParsedResult, extractJsonFromText

def test_extract_json_clean():
    res = extractJsonFromText('{"full_name": "Alice"}')
    assert res == {"full_name": "Alice"}

def test_extract_json_fenced():
    res = extractJsonFromText('```json\n{"full_name": "Bob"}\n```')
    assert res == {"full_name": "Bob"}

def test_extract_json_trailing_commas():
    res = extractJsonFromText('{"full_name": "Carol", "skills": ["Python", "JS", ], }')
    assert res == {"full_name": "Carol", "skills": ["Python", "JS"]}

def test_extract_json_invalid():
    with pytest.raises(ValueError, match="No JSON in model response"):
        extractJsonFromText("No JSON here")

def test_validate_parsed_result():
    assert validateParsedResult(None) == {'valid': False, 'errors': ['Response is not an object']}
    
    valid_data = {
        "full_name": "Alice",
        "contact": None,
        "email": "alice@example.com",
        "skills": ["Python"]
    }
    assert validateParsedResult(valid_data) == {'valid': True, 'errors': []}

    invalid_data = {
        "full_name": 123,
        "skills": "Python"
    }
    res = validateParsedResult(invalid_data)
    assert res['valid'] is False
    assert "full_name must be a string or null" in res['errors']
    assert "skills must be an array" in res['errors']

