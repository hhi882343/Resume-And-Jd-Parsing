"""
JSON response schema validation and extraction for Gemini output.
"""
from typing import Any, Dict, List
import json
from src.jsRegex import compile_re, js_trim

RE_FENCE = compile_re(r'```(?:json)?\s*([\s\S]*?)```', 'i')
RE_TRAILING_COMMA_OBJ = compile_re(r',\s*}', 'g')
RE_TRAILING_COMMA_ARR = compile_re(r',\s*]', 'g')


def validate_parsed_result(data: Any) -> Dict[str, Any]:
    errors: List[str] = []

    if not isinstance(data, dict) or data is None:
        return {'valid': False, 'errors': ['Response is not an object']}

    string_fields = [
        'full_name',
        'contact',
        'email',
        'linkedin',
        'qualification',
        'total_experience',
        'relevant_experience',
        'role',
        'location',
        'current_location',
        'current_employer',
    ]

    for field in string_fields:
        val = data.get(field)
        if val is not None and not isinstance(val, str):
            errors.append(f"{field} must be a string or null")

    for field in ['skills', 'technology', 'work_periods', 'relevant_work_periods']:
        val = data.get(field)
        if val is not None and not isinstance(val, list):
            errors.append(f"{field} must be an array")

    return {'valid': len(errors) == 0, 'errors': errors}


def extract_json_from_text(raw: str) -> Any:
    trimmed_raw = js_trim(raw) if raw is not None else ''
    if not trimmed_raw:
        raise ValueError('No JSON in model response')

    text = trimmed_raw

    fence_match = RE_FENCE.search(text)
    if fence_match and fence_match.group(1):
        text = js_trim(fence_match.group(1))

    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end < start:
        raise ValueError('No JSON in model response')

    slice_str = text[start:end + 1]

    try:
        return json.loads(slice_str)
    except Exception:
        repaired = RE_TRAILING_COMMA_OBJ.sub('}', slice_str)
        repaired = RE_TRAILING_COMMA_ARR.sub(']', repaired)
        try:
            return json.loads(repaired)
        except Exception:
            raise ValueError(f"Failed to parse JSON response: {slice_str[:100]}...")


# Aliases for JS export names
validateParsedResult = validate_parsed_result
extractJsonFromText = extract_json_from_text

