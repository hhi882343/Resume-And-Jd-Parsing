"""Pure-Python multi-requirement chunking and position-focus detection ported from TypeScript.

Ports exact logic from:
- src/lib/requirement-chunks.ts
- src/lib/multi-requirement-detector.ts
- src/lib/jd-utils.ts (regexAugment & extractCommonMetadata)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.core.normalize import (
    company_from_email,
    is_missing_field,
    map_relevant_experience,
)
from app.core.reward import (
    JS_WS_CLASS,
    js_trim,
    utf16_len,
    utf16_slice,
)

if TYPE_CHECKING:
    from app.schemas.requirement import RequirementData


def strip_footer(raw_text: str) -> str:
    """Strip standard email sign-offs, disclaimers, and footers matching TS stripFooter."""
    regards_match = re.search(
        rf"\n{JS_WS_CLASS}*Regards,?(?:{JS_WS_CLASS}*\n)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if regards_match:
        return js_trim(raw_text[: regards_match.start()])

    disclaimer_match = re.search(
        rf"\n{JS_WS_CLASS}*Disclaimer:",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if disclaimer_match:
        return js_trim(raw_text[: disclaimer_match.start()])

    return js_trim(raw_text)


def extract_email_headers(raw_text: str) -> str:
    """Extract standard email header lines matching TS extractEmailHeaders."""
    lines: List[str] = []
    for prefix in ["From:", "Sent:", "To:", "Cc:", "Subject:"]:
        pattern = rf"(?:\A|(?<=[\r\n\u2028\u2029])){prefix}{JS_WS_CLASS}*[^\r\n\u2028\u2029]+"
        match = re.search(pattern, raw_text, re.IGNORECASE | re.ASCII)
        if match:
            lines.append(js_trim(match.group(0)))
    return "\n".join(lines)


def infer_title_from_focus(num: str, focus: str, base_content: str) -> str:
    """Infer specialized role title from focus description or email Subject matching TS inferTitleFromFocus."""
    lower = focus.lower()
    if "fi" in lower and ("banking" in lower or "fscm" in lower):
        return "SAP FI Consultant (Banking & FSCM)"
    if "costing" in lower or "co-pa" in lower or "product costing" in lower:
        return "SAP CO Consultant (Product Costing & CO-PA)"

    subject_match = re.search(
        rf"Subject:{JS_WS_CLASS}*([^\r\n\u2028\u2029]+)",
        base_content,
        re.IGNORECASE | re.ASCII,
    )
    if subject_match:
        subject = subject_match.group(1)
        title_part = js_trim(subject.split("@")[0])
        if len(title_part) > 0:
            return f"{title_part} — Position {num}"

    return f"Position {num}"


def detect_position_focus_variants(raw_text: str) -> Optional[List[Dict[str, Any]]]:
    """Detect 'Position 1 to be focused ... Position 2 to be focused ...' role variants matching TS."""
    text = strip_footer(raw_text)
    pattern = re.compile(
        rf"Position{JS_WS_CLASS}+([0-9]+){JS_WS_CLASS}+to be focused{JS_WS_CLASS}+([\s\S]+?)(?={JS_WS_CLASS}*Position{JS_WS_CLASS}+[0-9]+{JS_WS_CLASS}+to be focused|\Z)",
        re.IGNORECASE | re.ASCII,
    )
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        return None

    base_end = matches[0].start()
    base_content = js_trim(utf16_slice(text, 0, base_end))
    openings_match = re.search(
        rf"\b([0-9]+){JS_WS_CLASS}+Openings?\b",
        base_content,
        re.IGNORECASE | re.ASCII,
    )
    total_openings = openings_match.group(1) if openings_match else None

    result: List[Dict[str, Any]] = []
    for m in matches:
        num = m.group(1)
        focus = js_trim(m.group(2))
        result.append(
            {
                "title": infer_title_from_focus(num, focus, base_content),
                "content": f"{base_content}\n\nPosition {num} to be focused {focus}",
                "numberOfPositions": total_openings,
            }
        )
    return result


def is_tiny_position_chunk(chunk: Dict[str, Any]) -> bool:
    """Check if chunk is a small position reference (< 500 characters) matching TS isTinyPositionChunk."""
    content = str(chunk.get("content", ""))
    trimmed = js_trim(content)
    is_pos = bool(re.match(rf"^Position{JS_WS_CLASS}+[0-9]+", trimmed, re.IGNORECASE | re.ASCII))
    return is_pos and utf16_len(content) < 500


def ensure_email_context(full_text: str, chunk_content: str) -> str:
    """Ensure chunk content retains top-level email headers matching TS ensureEmailContext."""
    has_from = bool(re.search(rf"From:{JS_WS_CLASS}*", chunk_content, re.IGNORECASE | re.ASCII))
    has_subject = bool(
        re.search(rf"Subject:{JS_WS_CLASS}*", chunk_content, re.IGNORECASE | re.ASCII)
    )
    if has_from and has_subject:
        return chunk_content

    headers = extract_email_headers(full_text)
    if len(headers) == 0:
        return chunk_content
    return f"{headers}\n\n{chunk_content}"


def split_requirements(raw_text: str) -> List[Dict[str, Any]]:
    """Split multi-role JDs by Requirement headers or tabular structures matching TS splitRequirements."""
    # Requirement #1, #2, #3
    if re.search(
        rf"Requirement{JS_WS_CLASS}*#{JS_WS_CLASS}*[0-9]+", raw_text, re.IGNORECASE | re.ASCII
    ):
        sections = re.split(
            rf"(?:Requirement{JS_WS_CLASS}*#{JS_WS_CLASS}*[0-9]+{JS_WS_CLASS}*:?{JS_WS_CLASS}*)",
            raw_text,
            flags=re.IGNORECASE | re.ASCII,
        )
        chunks: List[Dict[str, Any]] = []
        for index, section in enumerate(sections[1:]):
            content = js_trim(section)
            if utf16_len(content) > 50:
                chunks.append(
                    {
                        "title": f"Requirement {index + 1}",
                        "content": content,
                    }
                )
        return chunks

    # Open Positions table style
    if "Role Name" in raw_text and "No. of People Needed" in raw_text:
        return [
            {
                "title": "Multi Requirement",
                "content": raw_text,
            }
        ]

    # Default single JD
    return [
        {
            "title": "Single Requirement",
            "content": raw_text,
        }
    ]


def post_process_chunks(
    raw_text: str,
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Enrich chunks with position focus variants, email context, and shared headers matching TS postProcessChunks."""
    position_variants = detect_position_focus_variants(raw_text)
    if position_variants is not None:
        return position_variants

    tiny_position_chunks = [c for c in chunks if is_tiny_position_chunk(c)]
    if len(tiny_position_chunks) >= 2:
        large_chunks = [c for c in chunks if utf16_len(str(c.get("content", ""))) >= 400]
        base_content = (
            large_chunks[0]["content"]
            if len(large_chunks) > 0 and large_chunks[0].get("content") is not None
            else strip_footer(raw_text)
        )
        openings_match = re.search(
            rf"\b([0-9]+){JS_WS_CLASS}+Openings?\b",
            raw_text,
            re.IGNORECASE | re.ASCII,
        )
        openings = (
            large_chunks[0].get("numberOfPositions")
            if len(large_chunks) > 0 and large_chunks[0].get("numberOfPositions") is not None
            else (openings_match.group(1) if openings_match else None)
        )

        return [
            {
                "title": tc["title"],
                "numberOfPositions": openings
                if openings is not None
                else tc.get("numberOfPositions"),
                "content": ensure_email_context(
                    raw_text,
                    f"{base_content}\n\n{js_trim(str(tc.get('content', '')))}",
                ),
            }
            for tc in tiny_position_chunks
        ]

    if len(chunks) == 1:
        return [
            {
                **chunks[0],
                "content": ensure_email_context(raw_text, str(chunks[0].get("content", ""))),
            }
        ]

    return [
        {
            **c,
            "content": ensure_email_context(raw_text, str(c.get("content", ""))),
        }
        for c in chunks
    ]


def extract_common_metadata(raw_text: str) -> Dict[str, Any]:
    """Extract shared email and document metadata matching TS extractCommonMetadata."""
    return regex_augment(raw_text, {})


def regex_augment(
    raw_text: str,
    data: Dict[str, Any] | RequirementData,
) -> Dict[str, Any]:
    """Augment ATS requirement data using deterministic regex patterns matching TS regexAugment.

    Preserves exact TS checks between raw input 'data' vs evolving 'augmented',
    including the known internalPocTo behavior.
    """
    raw_data: Dict[str, Any] = (
        data.model_dump(by_alias=True) if hasattr(data, "model_dump") else dict(data)
    )
    augmented: Dict[str, Any] = {**raw_data}

    # 1. From: header
    from_match = re.search(
        rf"From:{JS_WS_CLASS}*([^\r\n\u2028\u2029]+)", raw_text, re.IGNORECASE | re.ASCII
    )
    if from_match:
        from_line_val = from_match.group(1)
        email_match = re.search(r"[A-Za-z0-9_.\+-]+@[A-Za-z0-9_.-]+\.[a-zA-Z]{2,}", from_line_val)
        from_name = (
            re.sub(r"<[^>]+>", "", from_line_val)
            .replace(email_match.group(0) if email_match else "", "")
            .strip()
        )
        if email_match:
            email_addr = email_match.group(0)
            if is_missing_field(augmented.get("clientLeadPocFrom")):
                augmented["clientLeadPocFrom"] = (
                    f"{from_name} <{email_addr}>" if len(from_name) > 0 else email_addr
                )
            if is_missing_field(augmented.get("clientPocFromCc")):
                augmented["clientPocFromCc"] = email_addr
            if is_missing_field(augmented.get("requirementFrom")):
                augmented["requirementFrom"] = company_from_email(email_addr)

    # 2. To: header
    to_match = re.search(
        rf"To:{JS_WS_CLASS}*([^\r\n\u2028\u2029]+)", raw_text, re.IGNORECASE | re.ASCII
    )
    if to_match and is_missing_field(augmented.get("internalPocTo")):
        augmented["internalPocTo"] = js_trim(to_match.group(1))

    # 3. Subject: header (jobTitle @ location)
    subject_match = re.search(
        rf"Subject:{JS_WS_CLASS}*([^\r\n\u2028\u2029]+)", raw_text, re.IGNORECASE | re.ASCII
    )
    if subject_match:
        subject = js_trim(subject_match.group(1))
        at_parts = [js_trim(p) for p in subject.split("@")]
        if (
            is_missing_field(augmented.get("jobTitle"))
            and len(at_parts) > 0
            and len(at_parts[0]) > 0
        ):
            augmented["jobTitle"] = at_parts[0]
        if (
            is_missing_field(augmented.get("location"))
            and len(at_parts) > 1
            and len(at_parts[1]) > 0
        ):
            augmented["location"] = at_parts[1]

    # 4. Sent: date
    sent_match = re.search(
        rf"Sent:{JS_WS_CLASS}*(?:[A-Za-z]+day,?(?:{JS_WS_CLASS}*))?([A-Za-z]+{JS_WS_CLASS}+[0-9]{{1,2}},?{JS_WS_CLASS}*[0-9]{{4}})(?:{JS_WS_CLASS}+([0-9]{{1,2}}:[0-9]{{2}}))?",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if sent_match and is_missing_field(raw_data.get("demandReceivedDate")):
        time_part = f", {sent_match.group(2)}" if sent_match.group(2) else ""
        augmented["demandReceivedDate"] = js_trim(f"{sent_match.group(1)}{time_part}")

    # 5. Openings inline
    openings_inline = re.search(
        rf"\b([0-9]+){JS_WS_CLASS}+openings?\b", raw_text, re.IGNORECASE | re.ASCII
    )
    if openings_inline:
        augmented["numberOfPositions"] = openings_inline.group(1)
        count = int(openings_inline.group(1))
        augmented["typeOfDemand"] = "Multiple" if count > 1 else "Single"

    # 6. Positions labeled header
    position_match = re.search(
        rf"(?:No\.?{JS_WS_CLASS}*of{JS_WS_CLASS}*Position[s]?|Number{JS_WS_CLASS}*of{JS_WS_CLASS}*Position[s]?|Headcount|Resources{JS_WS_CLASS}*Required){JS_WS_CLASS}*[\r\n\t :\-]*([0-9]+)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if position_match and is_missing_field(augmented.get("numberOfPositions")):
        augmented["numberOfPositions"] = position_match.group(1)
        count = int(position_match.group(1))
        augmented["typeOfDemand"] = "Multiple" if count > 1 else "Single"

    # 7. Overall experience
    exp_match = re.search(
        rf"overall{JS_WS_CLASS}*exp(?:erience)?{JS_WS_CLASS}*[-–:]{JS_WS_CLASS}*([0-9\t\n\x0b\x0c\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff\-–to]+years?)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if exp_match and is_missing_field(raw_data.get("overallExperience")):
        augmented["overallExperience"] = js_trim(
            re.sub(rf"{JS_WS_CLASS}+", " ", exp_match.group(1))
        )

    # 8. TPC Rates (monthly budget)
    tpc_match = re.search(
        rf"tpc{JS_WS_CLASS}*rates?{JS_WS_CLASS}*[-–:]{JS_WS_CLASS}*([0-9,]+)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if tpc_match and is_missing_field(raw_data.get("monthlyBudget")):
        augmented["monthlyBudget"] = f"INR {tpc_match.group(1)}"
        augmented["budgetCurrency"] = "INR"

    # 8b. Bill Rate / Rate card / Monthly Budget / Rate pm
    monthly_match = re.search(
        rf"(?:bill{JS_WS_CLASS}*rates?|rate{JS_WS_CLASS}*cards?|monthly{JS_WS_CLASS}*budget|rate{JS_WS_CLASS}*/{JS_WS_CLASS}*pm|budget{JS_WS_CLASS}*\({JS_WS_CLASS}*monthly{JS_WS_CLASS}*\)){JS_WS_CLASS}*[-–:]{JS_WS_CLASS}*([0-9,]+(?:\s*[-–to]+\s*[0-9,]+)?(?:\s*max)?)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if monthly_match and is_missing_field(augmented.get("monthlyBudget")):
        augmented["monthlyBudget"] = monthly_match.group(1).strip()
        if is_missing_field(augmented.get("budgetCurrency")):
            augmented["budgetCurrency"] = "INR"

    # 8c. Budget with monthly suffix (e.g. Budget: 70000 Monthly, Budget: 70000/month, Budget: 70000 pm)
    budget_month_match = re.search(
        rf"budget{JS_WS_CLASS}*[-–:]{JS_WS_CLASS}*([0-9,]+(?:\s*[-–to]+\s*[0-9,]+)?){JS_WS_CLASS}*(?:monthly|per{JS_WS_CLASS}*month|/{JS_WS_CLASS}*month|/{JS_WS_CLASS}*pm|pm\b)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if budget_month_match and is_missing_field(augmented.get("monthlyBudget")):
        augmented["monthlyBudget"] = budget_month_match.group(1).strip()
        if is_missing_field(augmented.get("budgetCurrency")):
            augmented["budgetCurrency"] = "INR"

    # 9. LPA match (annual budget)
    lpa_match = re.search(
        rf"([0-9]+{JS_WS_CLASS}*(?:to|-){JS_WS_CLASS}*[0-9]+){JS_WS_CLASS}*lpa",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if lpa_match and is_missing_field(augmented.get("annualBudget")):
        augmented["annualBudget"] = f"{lpa_match.group(1)} LPA"
        augmented["budgetCurrency"] = "INR"

    # 10. IS2 budget match
    is2_match = re.search(
        rf"is2{JS_WS_CLASS}*[-–:]{JS_WS_CLASS}*([0-9]+(?:{JS_WS_CLASS}*to{JS_WS_CLASS}*[0-9]+)?{JS_WS_CLASS}*lpa)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if is2_match:
        is2_val = js_trim(is2_match.group(1))
        if is_missing_field(augmented.get("annualBudget")):
            augmented["annualBudget"] = is2_val
            augmented["budgetCurrency"] = "INR"
        elif "is2" not in str(augmented.get("annualBudget", "")).lower():
            augmented["annualBudget"] = f"{augmented['annualBudget']} (IS2: {is2_val})"

    # 11. Immediate joiners
    if re.search(
        rf"immediate{JS_WS_CLASS}*joiners?", raw_text, re.IGNORECASE | re.ASCII
    ) and is_missing_field(raw_data.get("noticePeriod")):
        augmented["noticePeriod"] = "Immediate joiners only"

    # 12. @ Mentions (Preserves known TS behavior: checks raw_data.internalPocTo)
    mentions = [
        js_trim(m.group(1))
        for m in re.finditer(
            rf"@([A-Za-z][A-Za-z0-9_.\t\n\x0b\x0c\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+?)(?={JS_WS_CLASS}*&|{JS_WS_CLASS}*on\b|[\n,]|\Z)",
            raw_text,
            re.ASCII,
        )
    ]
    if len(mentions) > 0 and is_missing_field(raw_data.get("internalPocTo")):
        augmented["internalPocTo"] = ", ".join(mentions)

    # 13. Priority
    if re.search(
        rf"on{JS_WS_CLASS}+priority|priority", raw_text, re.IGNORECASE | re.ASCII
    ) and is_missing_field(raw_data.get("priority")):
        augmented["priority"] = "HIGH"

    # 14. Work mode
    if re.search(
        rf"hybrid{JS_WS_CLASS}*mode", raw_text, re.IGNORECASE | re.ASCII
    ) and is_missing_field(raw_data.get("workMode")):
        hybrid_detail = re.search(
            rf"hybrid{JS_WS_CLASS}*mode{JS_WS_CLASS}*\(([^)]+)\)",
            raw_text,
            re.IGNORECASE | re.ASCII,
        )
        augmented["workMode"] = f"Hybrid ({hybrid_detail.group(1)})" if hybrid_detail else "Hybrid"
    elif re.search(r"on-?site", raw_text, re.IGNORECASE | re.ASCII) and is_missing_field(
        raw_data.get("workMode")
    ):
        augmented["workMode"] = "On-site"
    elif re.search(r"\bremote\b", raw_text, re.IGNORECASE | re.ASCII) and is_missing_field(
        raw_data.get("workMode")
    ):
        augmented["workMode"] = "Remote"

    # 15. Work timings
    timings_match = re.search(
        rf"work{JS_WS_CLASS}*timings?{JS_WS_CLASS}*[-–:]{JS_WS_CLASS}*([^\r\n\u2028\u2029]+?)(?:\n|\Z)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if timings_match and is_missing_field(raw_data.get("workTimings")):
        augmented["workTimings"] = js_trim(timings_match.group(1))

    # 16. Contract
    if re.search(r"\bcontract\b", raw_text, re.IGNORECASE | re.ASCII) and is_missing_field(
        raw_data.get("employmentType")
    ):
        augmented["employmentType"] = "Contract"

    # 17. Pos count -> typeOfDemand (matches JS parseInt(String(augmented.numberOfPositions ?? data.numberOfPositions ?? ""), 10))
    pos_count_val = augmented.get("numberOfPositions") or raw_data.get("numberOfPositions", "")
    m_pos = re.match(r"^\s*([+-]?\d+)", str(pos_count_val))
    if m_pos:
        try:
            pos_int = int(m_pos.group(1))
            if is_missing_field(raw_data.get("typeOfDemand")):
                augmented["typeOfDemand"] = "Single" if pos_int == 1 else "Multiple"
        except (ValueError, TypeError):
            pass

    # 18. Overall exp -> relevant exp
    if (
        augmented.get("overallExperience")
        and not is_missing_field(augmented["overallExperience"])
        and is_missing_field(raw_data.get("relevantExperience"))
    ):
        augmented["relevantExperience"] = map_relevant_experience(
            str(augmented["overallExperience"])
        )

    # 19. Location
    location_match = re.search(
        rf"(?:Location|Work{JS_WS_CLASS}*Location|Job{JS_WS_CLASS}*Location|Base{JS_WS_CLASS}*Location){JS_WS_CLASS}*[\r\n\t :\-]*([A-Za-z\/ ,]+)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if location_match and is_missing_field(augmented.get("location")):
        augmented["location"] = js_trim(location_match.group(1))

    city_line_match = re.search(
        rf"\n([A-Z][a-zA-Z]+(?:{JS_WS_CLASS}*,{JS_WS_CLASS}*[A-Z][a-zA-Z]+)+){JS_WS_CLASS}*\n(?=Hybrid|Remote|On-?site|[0-9]+{JS_WS_CLASS}+Openings|Work{JS_WS_CLASS}*Timings)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if city_line_match and is_missing_field(augmented.get("location")):
        augmented["location"] = js_trim(city_line_match.group(1))

    # 20. Qualification
    qualification_match = re.search(
        rf"qualification{JS_WS_CLASS}*[-–:]{JS_WS_CLASS}*([^\r\n\u2028\u2029]+?)(?:\n|\Z)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if qualification_match and is_missing_field(raw_data.get("qualificationCriteria")):
        augmented["qualificationCriteria"] = js_trim(qualification_match.group(1))

    # 21. Alternative experience
    experience_match = re.search(
        rf"experience{JS_WS_CLASS}*[-–:]{JS_WS_CLASS}*([^\r\n\u2028\u2029]+?)(?:\n|\Z)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if experience_match and is_missing_field(raw_data.get("overallExperience")):
        augmented["overallExperience"] = js_trim(experience_match.group(1))

    # 22. Alternative monthly bill rate
    bill_rate_match = re.search(
        rf"bill{JS_WS_CLASS}*rate{JS_WS_CLASS}*per{JS_WS_CLASS}*month{JS_WS_CLASS}*[-–:]{JS_WS_CLASS}*([^\r\n\u2028\u2029]+?)(?:\n|\Z)",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if bill_rate_match and is_missing_field(raw_data.get("monthlyBudget")):
        augmented["monthlyBudget"] = js_trim(bill_rate_match.group(1))
        if is_missing_field(raw_data.get("budgetCurrency")):
            augmented["budgetCurrency"] = "INR"

    # 23. Employment type / Type of hire
    hire_type_match = re.search(
        rf"(?:Type{JS_WS_CLASS}*of{JS_WS_CLASS}*Hire|Employment{JS_WS_CLASS}*Type){JS_WS_CLASS}*[\r\n\t :\-]*((?:FTE|FTS|Sub-Con|Contract|Permanent))",
        raw_text,
        re.IGNORECASE | re.ASCII,
    )
    if hire_type_match:
        augmented["employmentType"] = hire_type_match.group(1)

    # 24. Cc: header
    cc_match = re.search(
        rf"Cc:{JS_WS_CLASS}*([^\r\n\u2028\u2029]+)", raw_text, re.IGNORECASE | re.ASCII
    )
    if cc_match and is_missing_field(raw_data.get("clientPocFromCc")):
        augmented["clientPocFromCc"] = js_trim(cc_match.group(1))

    return augmented
