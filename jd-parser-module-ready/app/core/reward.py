"""Pure-Python reward scoring engine ported directly from TypeScript src/lib/reward.ts.

Calculates field-weighted reward scores and F1 skill scores for RL feedback
and DPO preference pair generation.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence

NOT_SPECIFIED = "Not specified"

# Explicit JavaScript-equivalent whitespace characters per ECMA-262:
# Includes ASCII \t, \n, \x0b, \x0c, \r, space, plus Unicode Zs spaces, line terminators, BOM.
# Excludes ASCII control characters \x1c-\x1f which Python str.strip() includes but JS does not.
JS_WHITESPACE_CHARS = (
    "\t\n\x0b\x0c\r "
    "\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
)
JS_WS_CLASS = r"[\t\n\x0b\x0c\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]"
JS_TRIM_RE = re.compile(rf"^{JS_WS_CLASS}+|{JS_WS_CLASS}+$")
JS_COLLAPSE_RE = re.compile(rf"{JS_WS_CLASS}+")


def js_trim(s: str) -> str:
    """Trim leading and trailing whitespace matching JavaScript String.prototype.trim()."""
    return JS_TRIM_RE.sub("", s)


def js_collapse_whitespace(s: str) -> str:
    """Collapse contiguous whitespace matching JavaScript replace(/\\s+/g, ' ')."""
    return JS_COLLAPSE_RE.sub(" ", s)


def utf16_len(s: str) -> int:
    """Calculate string length in UTF-16 code units matching JavaScript String.prototype.length."""
    return len(s.encode("utf-16-le")) // 2


def utf16_slice(s: str, start: Optional[int] = None, end: Optional[int] = None) -> str:
    """Slice string using UTF-16 code unit indices matching JavaScript String.prototype.slice()."""
    encoded = s.encode("utf-16-le")
    total_units = len(encoded) // 2

    if start is None:
        start_byte = 0
    else:
        if start < 0:
            start = max(0, total_units + start)
        start_byte = min(total_units, start) * 2

    if end is None:
        end_byte = len(encoded)
    else:
        if end < 0:
            end = max(0, total_units + end)
        end_byte = min(total_units, end) * 2

    if start_byte >= end_byte:
        return ""
    return encoded[start_byte:end_byte].decode("utf-16-le", errors="ignore")


def _js_number_to_string(value: float | int) -> str:
    """Format float/int matching ECMAScript Number::toString()."""
    if value == 0:
        return "0"

    # Numbers exceeding JS MAX_SAFE_INTEGER (2^53 - 1) parsed via IEEE-754 double
    if isinstance(value, int) and (value > 9007199254740991 or value < -9007199254740991):
        value = float(value)

    if isinstance(value, int):
        return str(value)

    f = float(value)
    if f == 0:
        return "0"

    sign = "-" if f < 0 else ""
    f = abs(f)

    s = repr(f)
    if "e" in s:
        mantissa, exp_s = s.split("e")
        exp = int(exp_s)
    else:
        mantissa = s
        exp = 0

    if mantissa.endswith(".0"):
        mantissa = mantissa[:-2]

    digits = mantissa.replace(".", "")
    if "." in mantissa:
        dec_idx = mantissa.index(".")
    else:
        dec_idx = len(mantissa)

    k = len(digits)
    n = exp + dec_idx

    # ECMA-262 Section 7.1.12.1 rules:
    if k <= n <= 21:
        return sign + digits + ("0" * (n - k))
    elif 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        return sign + "0." + ("0" * (-n)) + digits
    else:
        if k == 1:
            a = digits
        else:
            a = digits[0] + "." + digits[1:]
        exp_sign = "+" if (n - 1) >= 0 else "-"
        return sign + a + "e" + exp_sign + str(abs(n - 1))


def js_string(value: Any) -> str:
    """Format value matching JavaScript String() coercion rules.

    - None -> "null"
    - True/False -> "true"/"false"
    - 1.0 -> "1", 1.5 -> "1.5"
    - 1e21 -> "1e+21", 12345678901234567890 -> "12345678901234567000"
    - lists -> items coerced and joined by comma (null items become "")
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _js_number_to_string(value)
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            if item is None:
                parts.append("")
            else:
                parts.append(js_string(item))
        return ",".join(parts)
    return str(value)


def _js_string_quote(val: str) -> str:
    """Quote string matching ECMAScript QuoteJSONString."""
    res = ['"']
    i = 0
    n = len(val)
    while i < n:
        c = val[i]
        code = ord(c)
        if 0xD800 <= code <= 0xDBFF and i + 1 < n and 0xDC00 <= ord(val[i + 1]) <= 0xDFFF:
            trail_code = ord(val[i + 1])
            full_codepoint = 0x10000 + ((code - 0xD800) << 10) + (trail_code - 0xDC00)
            res.append(chr(full_codepoint))
            i += 2
            continue

        if c == '"':
            res.append('\\"')
        elif c == "\\":
            res.append("\\\\")
        elif c == "\b":
            res.append("\\b")
        elif c == "\t":
            res.append("\\t")
        elif c == "\n":
            res.append("\\n")
        elif c == "\f":
            res.append("\\f")
        elif c == "\r":
            res.append("\\r")
        elif code < 0x20:
            res.append(f"\\u{code:04x}")
        elif 0xD800 <= code <= 0xDFFF:
            res.append(f"\\u{code:04x}")
        else:
            res.append(c)
        i += 1
    res.append('"')
    return "".join(res)


def js_json_stringify(value: Any) -> str:
    """Format data structure matching ECMAScript JSON.stringify() byte-for-byte.

    Rules:
    - None -> null
    - True/False -> true/false
    - int/float -> formatted with ECMAScript Number::toString rules (1.0 -> 1, 0.0 -> 0)
    - float NaN / Infinity -> null
    - str -> QuoteJSONString with lone surrogates escaped as \\udxxx
    - list/tuple -> [elem1,elem2,...]
    - dict -> {key1:val1,key2:val2,...} in exact insertion order
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return "null"
        return _js_number_to_string(value)
    if isinstance(value, str):
        return _js_string_quote(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(js_json_stringify(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                f"{_js_string_quote(str(k))}:{js_json_stringify(v)}" for k, v in value.items()
            )
            + "}"
        )
    if hasattr(value, "model_dump"):
        return js_json_stringify(value.model_dump(by_alias=True))
    return _js_string_quote(str(value))


FIELD_WEIGHTS: Dict[str, float] = {
    "jobTitle": 2.0,
    "location": 1.5,
    "numberOfPositions": 1.5,
    "annualBudget": 1.5,
    "monthlyBudget": 1.0,
    "workMode": 1.0,
    "workTimings": 1.0,
    "overallExperience": 1.0,
    "clientLeadPocFrom": 1.0,
    "internalPocTo": 1.0,
    "requirementFrom": 1.0,
    "demandReceivedDate": 1.0,
    "mandatorySkills": 2.0,
    "skills": 1.0,
    "employmentType": 0.8,
    "priority": 0.8,
    "qualificationCriteria": 0.8,
    "noticePeriod": 0.8,
    "budgetCurrency": 0.5,
    "typeOfDemand": 0.5,
    "relevantExperience": 0.5,
    "clientPocFromCc": 0.5,
    "sla": 0.3,
    "jobStatus": 0.3,
    "closedDate": 0.3,
    "openSince": 0.2,
    "jobDescription": 0.2,
}

SCORED_FIELDS: List[str] = list(FIELD_WEIGHTS.keys())
TOTAL_WEIGHT: float = sum(FIELD_WEIGHTS.values())


def normalize_string(value: str) -> str:
    """Normalize string matching TS value.trim().toLowerCase().replace(/\\s+/g, ' ')."""
    trimmed = js_trim(value).lower()
    return js_collapse_whitespace(trimmed)


def score_string(predicted: str, corrected: str) -> float:
    """Calculate string similarity score matching TypeScript scoreString exactly."""
    p = normalize_string(predicted)
    c = normalize_string(corrected)

    if p == c:
        return 1.0

    if p == NOT_SPECIFIED.lower() and c != NOT_SPECIFIED.lower():
        return 0.0

    # Partial credit only when strings significantly overlap by length
    if c in p or p in c:
        shorter = min(len(p), len(c))
        longer = max(len(p), len(c))
        if longer == 0:
            return 1.0
        # >=50% overlap -> 0.8 credit; otherwise 0.3 (some signal but not great)
        return 0.8 if (shorter / longer) >= 0.5 else 0.3

    return 0.0


def score_skills(predicted: Sequence[str], corrected: Sequence[str]) -> float:
    """Calculate F1 overlap score between predicted and corrected skills matching TS scoreSkills."""
    # User cleared all skills the model predicted -> model was completely wrong
    if len(corrected) == 0 and len(predicted) > 0:
        return 0.0

    # Both empty -> correct
    if len(corrected) == 0 and len(predicted) == 0:
        return 1.0

    # Model predicted nothing but user added skills -> model missed everything
    if len(predicted) == 0:
        return 0.0

    pred_set = {normalize_string(str(s)) for s in predicted}
    corr_set = {normalize_string(str(s)) for s in corrected}

    hits = 0
    for skill in corr_set:
        if skill in pred_set:
            hits += 1

    precision = hits / len(pred_set)
    recall = hits / len(corr_set)

    if precision + recall == 0.0:
        return 0.0

    return (2.0 * precision * recall) / (precision + recall)


def _get_field_value(data: Any, field_name: str) -> Any:
    """Extract field value from dictionary or model, supporting camelCase and snake_case."""
    if isinstance(data, dict):
        if field_name in data:
            return data[field_name]
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", field_name).lower()
        return data.get(snake)
    if hasattr(data, "model_dump"):
        dumped = data.model_dump(by_alias=True)
        if field_name in dumped:
            return dumped[field_name]
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", field_name).lower()
    return getattr(data, snake, getattr(data, field_name, None))


def compute_reward(predicted: Any, corrected: Any) -> Dict[str, Any]:
    """Calculate field-level and composite reward score between predicted and corrected requirements.

    Composite score is clamped to [0.0, 1.0] with NO rounding in calculation.
    Returns strictly snake_case keys: {"score": float, "field_rewards": Dict[str, float]}.
    """
    field_rewards: Dict[str, float] = {}
    weighted_sum = 0.0
    total_weight = 0.0

    for field in SCORED_FIELDS:
        weight = FIELD_WEIGHTS.get(field, 1.0)
        p_val = _get_field_value(predicted, field)
        c_val = _get_field_value(corrected, field)

        if field in ("mandatorySkills", "skills"):
            p_skills = list(p_val) if p_val is not None and isinstance(p_val, (list, tuple)) else []
            c_skills = list(c_val) if c_val is not None and isinstance(c_val, (list, tuple)) else []
            reward = score_skills(p_skills, c_skills)
        else:
            # TS: String(predicted[field] ?? "")
            p_str = "" if p_val is None else js_string(p_val)
            c_str = "" if c_val is None else js_string(c_val)
            reward = score_string(p_str, c_str)

        field_rewards[field] = reward
        weighted_sum += reward * weight
        total_weight += weight

    raw_score = (weighted_sum / total_weight) if total_weight > 0.0 else 1.0
    clamped_score = max(0.0, min(1.0, raw_score))

    return {
        "score": clamped_score,
        "field_rewards": field_rewards,
    }


def has_meaningful_diff(predicted: Any, corrected: Any) -> bool:
    """Check if correction differs from prediction beyond threshold score < 0.98."""
    return compute_reward(predicted, corrected)["score"] < 0.98
