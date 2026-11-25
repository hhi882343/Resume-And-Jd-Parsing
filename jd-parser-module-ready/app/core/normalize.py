"""Pure-Python normalization and ATS domain helpers ported directly from src/lib/jd-utils.ts."""

from __future__ import annotations

import json
import math
import random
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from app.core import clock
from app.core.reward import (
    JS_WS_CLASS,
    js_string,
    js_trim,
    utf16_slice,
)

if TYPE_CHECKING:
    from app.schemas.requirement import RequirementData

NOT_SPECIFIED = "Not specified"

GENERIC_TITLES: Set[str] = {
    "not specified",
    "single requirement",
    "multi requirement",
    "requirement",
    "n/a",
    "na",
    "tbd",
    "to be determined",
    "job title",
    "role",
    "position",
}

INHERITABLE_STRING_FIELDS: List[str] = [
    "clientLeadPocFrom",
    "clientPocFromCc",
    "internalPocTo",
    "requirementFrom",
    "demandReceivedDate",
    "typeOfDemand",
    "priority",
    "relevantExperience",
    "overallExperience",
    "qualificationCriteria",
    "employmentType",
    "workMode",
    "workTimings",
    "location",
    "numberOfPositions",
    "budgetCurrency",
    "monthlyBudget",
    "annualBudget",
    "noticePeriod",
    "sla",
]


def is_generic_job_title(title: str) -> bool:
    """Check if job title is missing or a generic ATS placeholder."""
    normalized = js_trim(title).lower()
    if len(normalized) == 0:
        return True
    if normalized in GENERIC_TITLES:
        return True
    if re.match(
        rf"(?a)\Arequirement{JS_WS_CLASS}*#?[0-9]*\Z", normalized, re.IGNORECASE | re.ASCII
    ):
        return True
    return False


def resolve_job_title(extracted_title: str, hint_title: Optional[str] = None) -> str:
    """Resolve job title using hint title if extracted title is generic."""
    if not is_generic_job_title(extracted_title):
        return extracted_title
    if hint_title is not None and not is_generic_job_title(hint_title):
        return hint_title
    return NOT_SPECIFIED


def normalize(value: Any) -> str:
    """Normalize untyped or dirty LLM input values to clean ATS strings."""
    if value is None:
        return NOT_SPECIFIED

    if isinstance(value, str):
        text = value
    elif isinstance(value, bool):
        # JavaScript String(true) -> "true", String(false) -> "false"
        text = "true" if value else "false"
    elif isinstance(value, (int, float)):
        text = js_string(value)
    elif isinstance(value, (list, tuple)):
        text = ", ".join(js_string(item) for item in value)
    elif isinstance(value, dict):
        text = json.dumps(value)
    else:
        return NOT_SPECIFIED

    trimmed = js_trim(text)
    if len(trimmed) == 0 or trimmed.lower() == "n/a" or trimmed == "-":
        return NOT_SPECIFIED
    return trimmed


def normalize_skills(skills: Any) -> List[str]:
    """Parse, clean, deduplicate, and normalize skill inputs."""
    items: List[Any] = []

    if isinstance(skills, (list, tuple)):
        items = list(skills)
    elif isinstance(skills, str) and len(js_trim(skills)) > 0:
        items = re.split(r"[,;|]", skills)

    if len(items) == 0:
        return []

    seen: Set[str] = set()
    result: List[str] = []
    for skill in items:
        cleaned = re.sub(rf"^[-•*]{JS_WS_CLASS}*", "", normalize(skill))
        if len(cleaned) == 0 or cleaned == NOT_SPECIFIED:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def generate_requirement_id() -> str:
    """Generate ATS requirement ID formatted as REQ-YYYY-MM-DD-SEQ.

    Uses application/local timezone matching TypeScript's new Date().getFullYear().
    """
    now = clock.local_now()
    y = now.strftime("%Y")
    m = now.strftime("%m")
    d = now.strftime("%d")
    seq = random.randint(100, 999)
    return f"REQ-{y}-{m}-{d}-{seq}"


def parse_date_js(date_str: str) -> Optional[int]:
    """Parse date string reproducing JavaScript's Date.parse(dateStr.replace(/,/g, '')).

    ECMAScript Date.parse rules:
    - ISO date-only format (YYYY-MM-DD) -> parsed as UTC.
    - ISO date-time with 'Z' or explicit offset -> parsed with that offset.
    - ISO date-time without offset -> parsed in local (APP_TIMEZONE) time.
    - Other non-ISO formats (e.g. 'May 15 2026', '15 May 2026', '05/15/2026') -> parsed in local (APP_TIMEZONE) time.
    Returns epoch milliseconds, or None if unparseable (matching NaN).
    """
    raw = date_str.replace(",", "").strip()
    if not raw:
        return None

    tz = clock.get_app_timezone()

    # 1. ISO date-only: YYYY-MM-DD -> UTC per ECMAScript spec
    m_iso_date = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", raw)
    if m_iso_date:
        dt = datetime(
            int(m_iso_date.group(1)),
            int(m_iso_date.group(2)),
            int(m_iso_date.group(3)),
            tzinfo=timezone.utc,
        )
        return int(dt.timestamp() * 1000)

    # 2. ISO date-time with Z or offset
    if "T" in raw and (raw.endswith("Z") or re.search(r"[+-]\d{2}:?\d{2}$", raw)):
        try:
            iso_str = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_str)
            return int(dt.timestamp() * 1000)
        except Exception:
            pass

    # 3. ISO date-time without offset -> LOCAL per ECMAScript spec
    if "T" in raw and re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$", raw):
        try:
            dt = datetime.fromisoformat(raw).replace(tzinfo=tz)
            return int(dt.timestamp() * 1000)
        except Exception:
            pass

    # 4. Other formats (legacy V8 / Node.js Date.parse) -> LOCAL
    clean = re.sub(
        r"^(?:Sent:\s*)?(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+)?",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()

    for fmt in [
        "%B %d %Y %I:%M %p",
        "%b %d %Y %I:%M %p",
        "%B %d %Y %H:%M",
        "%b %d %Y %H:%M",
        "%B %d %Y",
        "%b %d %Y",
        "%d %B %Y %I:%M %p",
        "%d %b %Y %I:%M %p",
        "%d %B %Y %H:%M",
        "%d %b %Y %H:%M",
        "%d %B %Y",
        "%d %b %Y",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ]:
        try:
            parsed = datetime.strptime(clean, fmt)
            dt = parsed.replace(tzinfo=tz)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue

    return None


def format_open_since(demand_date: str) -> str:
    """Compute days elapsed since demand_date and format as '<date> (<N> days)'.

    Ported verbatim from src/lib/jd-utils.ts lines 156-166.
    """
    if demand_date == NOT_SPECIFIED:
        return NOT_SPECIFIED

    parsed_ms = parse_date_js(demand_date)
    if parsed_ms is None:
        return demand_date

    now_ms = int(clock.now().timestamp() * 1000)
    days = max(0, math.floor((now_ms - parsed_ms) / (1000 * 60 * 60 * 24)))
    date_part = ", ".join([part.strip() for part in demand_date.split(",")[:2]]).strip()
    day_str = "day" if days == 1 else "days"
    return f"{date_part} ({days} {day_str})"


def map_relevant_experience(years_text: str) -> str:
    """Map raw experience range string to ATS seniority category."""
    match = re.search(r"([0-9]+)", years_text, re.ASCII)
    if not match:
        return NOT_SPECIFIED
    min_years = int(match.group(1))
    if min_years < 2:
        return "Junior"
    if min_years < 5:
        return "Mid"
    if min_years < 8:
        return "Mid Senior"
    return "Senior"


def company_from_email(email: str) -> str:
    """Extract and format client company name from email address."""
    parts = email.split("@")
    if len(parts) < 2 or len(parts[1]) == 0:
        return NOT_SPECIFIED
    domain = parts[1].split(".")[0]
    if len(domain) == 0:
        return NOT_SPECIFIED
    return domain.replace("-", " ").upper()


def split_skill_list(raw: str) -> List[str]:
    """Split delimited string of skills and trim elements."""
    return [js_trim(s) for s in re.split(r"[,;|]", raw) if len(js_trim(s)) > 0]


def extract_job_description_section(raw_text: str) -> str:
    """Extract role overview or description section up to 3000 chars."""
    match = re.search(
        rf"(?:job{JS_WS_CLASS}*description|key{JS_WS_CLASS}*areas?{JS_WS_CLASS}*of{JS_WS_CLASS}*responsibility|role{JS_WS_CLASS}*overview|key{JS_WS_CLASS}*responsibilities?){JS_WS_CLASS}*:?{JS_WS_CLASS}*([\s\S]+)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if not match:
        return NOT_SPECIFIED
    return utf16_slice(js_trim(match.group(1)), 0, 3000)


def is_missing_field(value: Any) -> bool:
    """Check if ATS field is empty, null, or set to 'Not specified'."""
    if value is None:
        return True
    if isinstance(value, str):
        trimmed = js_trim(value)
        return len(trimmed) == 0 or trimmed == NOT_SPECIFIED
    return False


def to_requirement_data(
    extracted: Dict[str, Any] | RequirementData,
    options: Optional[Dict[str, Any]] = None,
) -> RequirementData:
    """Convert partial or dirty extracted dict into fully normalized RequirementData object."""
    from app.schemas.requirement import RequirementData

    data = (
        extracted.model_dump(by_alias=True)
        if isinstance(extracted, RequirementData)
        else dict(extracted)
    )

    demand_received_date = normalize(
        data.get("demandReceivedDate", data.get("demand_received_date"))
    )
    mandatory_skills = normalize_skills(data.get("mandatorySkills", data.get("mandatory_skills")))
    skills = normalize_skills(data.get("skills"))
    final_skills = skills if len(skills) > 0 else mandatory_skills

    is_inferred = (
        options.get("isInferredTitle")
        if options is not None
        else data.get("isInferredTitle", data.get("is_inferred_title"))
    )

    return RequirementData(
        requirement_id=generate_requirement_id(),
        job_title=normalize(data.get("jobTitle", data.get("job_title"))),
        is_inferred_title=is_inferred,
        client_lead_poc_from=normalize(
            data.get("clientLeadPocFrom", data.get("client_lead_poc_from"))
        ),
        client_poc_from_cc=normalize(data.get("clientPocFromCc", data.get("client_poc_from_cc"))),
        internal_poc_to=normalize(data.get("internalPocTo", data.get("internal_poc_to"))),
        requirement_from=normalize(data.get("requirementFrom", data.get("requirement_from"))),
        demand_received_date=demand_received_date,
        closed_date=NOT_SPECIFIED,
        open_since=format_open_since(demand_received_date),
        type_of_demand=normalize(data.get("typeOfDemand", data.get("type_of_demand"))),
        job_status="Unassigned",
        priority=normalize(data.get("priority")),
        relevant_experience=normalize(
            data.get("relevantExperience", data.get("relevant_experience"))
        ),
        overall_experience=normalize(data.get("overallExperience", data.get("overall_experience"))),
        qualification_criteria=normalize(
            data.get("qualificationCriteria", data.get("qualification_criteria"))
        ),
        employment_type=normalize(data.get("employmentType", data.get("employment_type"))),
        work_mode=normalize(data.get("workMode", data.get("work_mode"))),
        work_timings=normalize(data.get("workTimings", data.get("work_timings"))),
        location=normalize(data.get("location")),
        number_of_positions=normalize(data.get("numberOfPositions", data.get("numberOfPositions"))),
        budget_currency=normalize(data.get("budgetCurrency", data.get("budget_currency"))),
        monthly_budget=normalize(data.get("monthlyBudget", data.get("monthly_budget"))),
        annual_budget=normalize(data.get("annualBudget", data.get("annual_budget"))),
        notice_period=normalize(data.get("noticePeriod", data.get("notice_period"))),
        sla=normalize(data.get("sla")),
        mandatory_skills=mandatory_skills,
        skills=final_skills,
        job_description=normalize(data.get("jobDescription", data.get("job_description"))),
    )


def merge_inherited_fields(
    role: RequirementData | Dict[str, Any],
    common: RequirementData | Dict[str, Any],
) -> RequirementData:
    """Fill missing role fields from shared JD/email metadata."""
    role_dict = role.model_dump(by_alias=True) if hasattr(role, "model_dump") else dict(role)
    common_dict = (
        common.model_dump(by_alias=True) if hasattr(common, "model_dump") else dict(common)
    )

    merged = {**role_dict}

    for field in INHERITABLE_STRING_FIELDS:
        role_val = merged.get(field)
        comm_val = common_dict.get(field)
        if is_missing_field(role_val) and not is_missing_field(comm_val):
            merged[field] = comm_val

    # Inherit skills if role has empty list
    role_m_skills = merged.get("mandatorySkills", [])
    comm_m_skills = common_dict.get("mandatorySkills", [])
    if len(role_m_skills) == 0 and len(comm_m_skills) > 0:
        merged["mandatorySkills"] = comm_m_skills

    role_s_skills = merged.get("skills", [])
    comm_s_skills = common_dict.get("skills", [])
    if len(role_s_skills) == 0 and len(comm_s_skills) > 0:
        merged["skills"] = comm_s_skills

    if (
        merged.get("jobDescription") == NOT_SPECIFIED
        and common_dict.get("jobDescription") is not None
        and common_dict.get("jobDescription") != NOT_SPECIFIED
    ):
        merged["jobDescription"] = common_dict["jobDescription"]

    demand_received_date = merged.get("demandReceivedDate")
    if demand_received_date is not None and demand_received_date != NOT_SPECIFIED:
        merged["openSince"] = format_open_since(demand_received_date)

    return to_requirement_data(merged)
