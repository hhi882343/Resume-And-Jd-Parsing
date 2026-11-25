"""
Normalization functions for candidate parsed results.
"""
from typing import Any, Dict, Optional, List
from src.ai.experience import resolve_experience_fields
from src.jsRegex import compile_re, js_trim

CC: List[str] = [
    '+971', '+966', '+974', '+968', '+965', '+973', '+972', '+44', '+91',
    '+61', '+49', '+33', '+81', '+86', '+65', '+60', '+62', '+64', '+1',
]

RE_PHONE_SPLIT = compile_re(r'\s*/\s*')
RE_WS = compile_re(r'\s+', 'g')
RE_FALLBACK_CC = compile_re(r'^(\+\d{2})(\d)')


def normalize_phone(raw: Optional[str]) -> str:
    if not raw:
        return ''

    parts = RE_PHONE_SPLIT.split(str(raw))
    results: List[str] = []

    for n in parts:
        t = js_trim(n)
        if not t.startswith('+'):
            results.append(t)
            continue

        flat = RE_WS.sub('', t)
        cc = next((c for c in CC if flat.startswith(c)), None)
        if cc:
            loc = flat[len(cc):]
            if len(loc) == 10:
                results.append(f"{cc} {loc[:5]} {loc[5:]}")
            else:
                results.append(f"{cc} {loc}")
        else:
            results.append(RE_FALLBACK_CC.sub(r'\1 \2', flat))

    return ' / '.join(results)


def normalize_parsed_result(r: Dict[str, Any]) -> Dict[str, Any]:
    exp = resolve_experience_fields(
        total_experience=r.get('total_experience'),
        relevant_experience=r.get('relevant_experience'),
        work_periods=r.get('work_periods'),
        relevant_work_periods=r.get('relevant_work_periods'),
    )

    skills_val = r.get('skills')
    tech_val = r.get('technology')

    out = {
        'full_name': r.get('full_name') or '',
        'contact': normalize_phone(r.get('contact')),
        'email': r.get('email') or '',
        'linkedin': r.get('linkedin') or '',
        'qualification': r.get('qualification') or '',
    }
    out.update(exp)
    out['skills'] = skills_val[:10] if isinstance(skills_val, list) else []
    out['technology'] = tech_val if isinstance(tech_val, list) else []
    out['role'] = js_trim(str(r.get('role') or ''))
    loc = js_trim(str(r.get('location') or r.get('current_location') or ''))
    out['location'] = loc if loc else None
    out['current_location'] = loc if loc else None
    emp = js_trim(str(r.get('current_employer') or r.get('company') or ''))
    out['current_employer'] = emp if emp else None

    return out


# Aliases for JS export names
normalizePhone = normalize_phone
normalizeParsedResult = normalize_parsed_result

