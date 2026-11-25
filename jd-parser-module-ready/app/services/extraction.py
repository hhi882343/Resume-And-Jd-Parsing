"""Extraction orchestration service ported directly from src/app/api/analyze/route.ts.

Coordinates:
- Split requirements detection (position focus, LLM, or regex heuristics)
- Per-chunk concurrent LLM extraction (asyncio.gather preserving chunk order)
- Missing field filling and domain normalization
- Regex heuristic augmentation
- Common metadata inheritance
- Human correction overlay loop
- Result metadata tagging (1-based roleIndex, totalRoles, extractionSource, correctionApplied)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.chunker import (
    detect_position_focus_variants,
    extract_common_metadata,
    post_process_chunks,
    regex_augment,
)
from app.core.email_extractor import extract_universal_email_headers
from app.core.normalize import (
    NOT_SPECIFIED,
    company_from_email,
    is_generic_job_title,
    merge_inherited_fields,
    resolve_job_title,
    to_requirement_data,
)
from app.core.overlay import apply_correction_overlay
from app.core.reward import js_string, js_trim
from app.schemas.analyze import AnalyzeResponse
from app.schemas.requirement import AnalyzedRequirement, RequirementData
from app.services.feedback import (
    AnalysisRolePayload,
    get_latest_corrections_for_jd,
    save_analysis_run,
    to_requirement_payload,
)
from app.services.llm_client import DEFAULT_HTTP_TIMEOUT, BaseLLMClient
from app.services.prompts import (
    JSON_FIELDS,
    RATE_LIMIT_MESSAGE,
    SKILL_FIELDS,
    SPLIT_REQUIREMENTS_PROMPT,
    build_gemini_extraction_prompt,
    build_split_prompt,
    build_title_inference_prompt,
)

logger = logging.getLogger(__name__)

RequirementChunk = Dict[str, Any]


class CorrectionLookup(Protocol):
    """Protocol for asynchronous correction lookup by raw JD text."""

    async def __call__(self, raw_jd_text: str) -> Dict[int, RequirementData]:
        """Look up latest corrections indexed by 1-based roleIndex."""
        ...


class AnalyzeRateLimitError(Exception):
    """Raised when an LLM API rate limit or service quota exhaustion occurs."""

    def __init__(
        self,
        message: str = "API rate limit exceeded. The system is retrying with alternative providers. Please try again in a few moments.",
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or RATE_LIMIT_MESSAGE
        self.is_rate_limit = True


class AnalyzeServiceError(Exception):
    """Generic error raised during requirement analysis orchestration."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class ExtractOptions:
    """Options passed to job requirement extraction matching TypeScript ExtractOptions."""

    hint_title: Optional[str] = None
    full_jd_text: Optional[str] = None
    sample_id: Optional[str] = None


@dataclass
class ExtractionResult:
    """Result of single job requirement extraction matching TypeScript ExtractionResult."""

    data: RequirementData
    source: str


def fill_missing_fields(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all 24 ATS JSON fields are present in LLM output dict.

    Ported verbatim from src/lib/llm-extract.ts lines 387-394.
    """
    for field in JSON_FIELDS:
        if field not in parsed or parsed[field] is None:
            parsed[field] = [] if field in SKILL_FIELDS else NOT_SPECIFIED
    return parsed


async def finalize_extraction(
    raw_jd_text: str,
    parsed: Dict[str, Any],
    options: Optional[ExtractOptions] = None,
    *,
    llm_client: Optional[BaseLLMClient] = None,
) -> RequirementData:
    """Clean, skill-deduplicate, regex-augment, and title-resolve extracted dictionary.

    Ported verbatim from src/lib/llm-extract.ts lines 330-385.
    """
    # 1. Normalize mandatory skills
    raw_mandatory = parsed.get("mandatorySkills")
    if isinstance(raw_mandatory, list):
        mandatory_array = [str(s) for s in raw_mandatory if s is not None and str(s).strip()]
    elif isinstance(raw_mandatory, str):
        import re

        mandatory_array = [s.strip() for s in re.split(r"[,;|]", raw_mandatory) if s.strip()]
    else:
        mandatory_array = []

    # 2. Normalize secondary skills
    raw_skills = parsed.get("skills")
    if isinstance(raw_skills, list):
        skill_array = [str(s) for s in raw_skills if s is not None and str(s).strip()]
    elif isinstance(raw_skills, str):
        import re

        skill_array = [s.strip() for s in re.split(r"[,;|]", raw_skills) if s.strip()]
    else:
        skill_array = []

    # Deduplicate secondary skills against mandatory skills
    mandatory_set = {s.lower().strip() for s in mandatory_array}
    parsed["mandatorySkills"] = mandatory_array
    parsed["skills"] = [s for s in skill_array if s.lower().strip() not in mandatory_set]

    # 3. Regex heuristic augmentation
    augment_source = options.full_jd_text if options and options.full_jd_text else raw_jd_text
    augmented = regex_augment(augment_source, parsed)

    # 4. Resolve Job Title
    raw_val = augmented.get("jobTitle")
    if isinstance(raw_val, list):
        raw_extracted_title = ",".join(js_string(x) for x in raw_val)
    elif raw_val is not None:
        raw_extracted_title = js_string(raw_val)
    else:
        raw_extracted_title = NOT_SPECIFIED
    hint_title = options.hint_title if options else None
    job_title = resolve_job_title(raw_extracted_title, hint_title)
    is_inferred_title = False

    if job_title == NOT_SPECIFIED:
        all_skills = [
            *mandatory_array,
            *[s for s in skill_array if s.lower().strip() not in mandatory_set],
        ]
        # In live mode if title inference is available
        if llm_client and hasattr(llm_client, "infer_job_title"):
            inferred = await getattr(llm_client, "infer_job_title")(raw_jd_text, all_skills)
            if inferred and not is_generic_job_title(inferred):
                job_title = inferred
                is_inferred_title = True
    elif is_generic_job_title(raw_extracted_title):
        is_inferred_title = True

    augmented["jobTitle"] = job_title

    return to_requirement_data(augmented, options={"isInferredTitle": is_inferred_title})


async def extract_job_requirement(
    raw_jd_text: str,
    options: Optional[ExtractOptions] = None,
    *,
    llm_client: BaseLLMClient,
) -> ExtractionResult:
    """Extract single requirement data via LLM client matching src/lib/extract-jd.ts."""
    prompt = build_gemini_extraction_prompt(
        raw_jd_text, hint_title=options.hint_title if options else None
    )

    try:
        if hasattr(llm_client, "extract_with_provider"):
            content, source = await getattr(llm_client, "extract_with_provider")(
                prompt,
                raw_text=raw_jd_text,
                sample_id=options.sample_id if options else None,
                json_mode=True,
            )
        else:
            content = await llm_client.extract(
                prompt,
                raw_text=raw_jd_text,
                sample_id=options.sample_id if options else None,
                json_mode=True,
            )
            source = llm_client.provider_name
    except Exception as exc:
        msg = str(exc)
        if any(
            term in msg
            for term in (
                "429",
                "503",
                "rate limit",
                "high demand",
                "Quota exceeded",
                "RATE_LIMIT_EXCEEDED",
                "All providers failed",
            )
        ):
            raise AnalyzeRateLimitError() from exc
        raise

    if not content or not content.strip():
        raise RuntimeError("Empty response from LLM")

    try:
        parsed_raw = json.loads(
            content,
            parse_constant=_reject_constant,
            parse_int=float,
            parse_float=float,
        )
        if not isinstance(parsed_raw, dict):
            raise ValueError("LLM response did not contain a JSON object")
    except Exception as exc:
        raise ValueError(f"Malformed JSON from LLM: {exc}") from exc

    filled = fill_missing_fields(parsed_raw)
    data = await finalize_extraction(raw_jd_text, filled, options, llm_client=llm_client)
    return ExtractionResult(data=data, source=source)


def _reject_constant(val: str) -> None:
    """Reject non-standard JSON constants (NaN, Infinity, -Infinity) matching JSON.parse."""
    raise ValueError(f"Invalid JSON constant: {val}")


async def infer_job_title_with_gemini(
    requirement_text: str,
    skills: Optional[List[str]] = None,
    *,
    llm_client: Optional[BaseLLMClient] = None,
) -> Optional[str]:
    """Infer professional job title using Gemini matching src/lib/gemini-helpers.ts:117-136."""
    skills_list = skills or []
    if llm_client and hasattr(llm_client, "infer_job_title"):
        return await getattr(llm_client, "infer_job_title")(requirement_text, skills_list)

    from app.config import settings

    if not settings.GEMINI_API_KEY or not settings.GEMINI_API_KEY.strip():
        return None

    try:
        prompt = build_title_inference_prompt(requirement_text, skills_list)
        from app.services.llm_client import GeminiClient

        client = llm_client or GeminiClient()
        content = await client.extract(prompt, raw_text=requirement_text, json_mode=True)
        parsed = json.loads(content, parse_constant=_reject_constant)
        if isinstance(parsed, dict):
            title = str(parsed.get("jobTitle") or "").strip()
            return title or None
    except Exception as exc:
        logger.warning(f"Gemini title inference failed: {exc}")
    return None


async def detect_requirements_with_llm(
    raw_text: str,
    *,
    llm_client: Optional[BaseLLMClient] = None,
) -> List[RequirementChunk]:
    """Detect and partition requirements matching src/lib/multi-requirement-llm.ts:114-255."""
    position_variants = detect_position_focus_variants(raw_text)
    if position_variants:
        return position_variants

    prompt = build_split_prompt(raw_text)

    # 1. Try Gemini (matching TS generateGeminiContent in multi-requirement-llm.ts:123)
    gemini_client = getattr(llm_client, "_gemini", llm_client) if llm_client else None
    if gemini_client:
        try:
            content = await gemini_client.extract(prompt, raw_text=raw_text, json_mode=True)
            if content and content.strip():
                parsed = json.loads(content, parse_constant=_reject_constant)
                reqs = parsed.get("requirements")
                if isinstance(reqs, list) and len(reqs) > 0:
                    return post_process_chunks(raw_text, reqs)
                return post_process_chunks(
                    raw_text, [{"title": "Single Requirement", "content": raw_text}]
                )
        except Exception as exc:
            logger.warning(f"Gemini splitter failed, falling back: {exc}")

    from app.config import settings

    # 2. Try Groq as second fallback (TS lines 149-200)
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip():
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_HTTP_TIMEOUT) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.GROQ_MODEL or "llama-3.3-70b-versatile",
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": SPLIT_REQUIREMENTS_PROMPT},
                            {"role": "user", "content": raw_text},
                        ],
                    },
                )
                payload = response.json()
                content = None
                if isinstance(payload, dict):
                    choices = payload.get("choices")
                    if isinstance(choices, list) and len(choices) > 0:
                        msg = choices[0].get("message")
                        if isinstance(msg, dict):
                            content = msg.get("content")
                if content:
                    parsed = json.loads(content, parse_constant=_reject_constant)
                    reqs = parsed.get("requirements") if isinstance(parsed, dict) else None
                    return post_process_chunks(
                        raw_text,
                        reqs
                        if isinstance(reqs, list)
                        else [{"title": "Single Requirement", "content": raw_text}],
                    )
        except Exception as exc:
            logger.warning(f"Groq splitter failed, falling back to SambaNova: {exc}")

    # 3. Fallback to SambaNova (TS lines 202-255: no try/catch around fetch)
    async with httpx.AsyncClient(timeout=DEFAULT_HTTP_TIMEOUT) as client:
        response = await client.post(
            "https://api.sambanova.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.SAMBANOVA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.SAMBANOVA_MODEL or "Meta-Llama-3.3-70B-Instruct",
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SPLIT_REQUIREMENTS_PROMPT},
                    {"role": "user", "content": raw_text},
                ],
            },
        )
        payload = response.json()
        content = None
        if isinstance(payload, dict):
            choices = payload.get("choices")
            if isinstance(choices, list) and len(choices) > 0:
                msg = choices[0].get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
        if not content:
            return post_process_chunks(
                raw_text, [{"title": "Single Requirement", "content": raw_text}]
            )
        parsed = json.loads(content, parse_constant=_reject_constant)
        reqs = parsed.get("requirements") if isinstance(parsed, dict) else None
        return post_process_chunks(
            raw_text,
            reqs
            if isinstance(reqs, list)
            else [{"title": "Single Requirement", "content": raw_text}],
        )


async def detect_requirements(
    raw_text: str,
    *,
    llm_client: Optional[BaseLLMClient] = None,
) -> List[RequirementChunk]:
    """Delegate to detect_requirements_with_llm."""
    return await detect_requirements_with_llm(raw_text, llm_client=llm_client)


async def orchestrate_analysis(
    raw_jd_text: str,
    *,
    llm_client: BaseLLMClient,
    correction_lookup: Optional[CorrectionLookup] = None,
    session: Optional[AsyncSession] = None,
    policy_version: str = "gemini-bootstrap",
) -> AnalyzeResponse:
    """Orchestrate full analysis pipeline matching src/app/api/analyze/route.ts.

    Steps:
    1. Validate input text.
    2. Look up prior human corrections (keys: 1-based roleIndex).
    3. Split requirements into distinct role chunks.
    4. Concurrently extract per-chunk requirement data (asyncio.gather).
    5. Merge inherited common metadata and position counts.
    6. Overlay prior human corrections.
    7. Tag metadata (1-based roleIndex, totalRoles, extractionSource, correctionApplied).
    8. Persist analysis run and per-role predictions when session is provided.
    """
    raw_jd_clean = js_trim(raw_jd_text)
    if not raw_jd_clean:
        raise ValueError("Job description text is required")

    started_at = time.time()

    # 1. Look up prior corrections
    prior_corrections: Dict[int, RequirementData] = {}
    if correction_lookup:
        try:
            prior_corrections = await correction_lookup(raw_jd_clean)
        except Exception as exc:
            logger.error(f"Correction lookup failed: {exc}")
            prior_corrections = {}
    elif session is not None:
        try:
            prior_corrections = await get_latest_corrections_for_jd(session, raw_jd_clean)
        except Exception as exc:
            logger.error(f"Correction lookup failed: {exc}")
            prior_corrections = {}

    if len(prior_corrections) > 0:
        logger.info(
            f"[RL overlay] Found prior corrections for {len(prior_corrections)} role(s) — applying to fresh extraction."
        )

    # 2. Partition JD into requirement chunks
    try:
        chunks = await detect_requirements(raw_jd_clean, llm_client=llm_client)
    except Exception as exc:
        msg = str(exc)
        if any(
            term in msg
            for term in (
                "429",
                "503",
                "rate limit",
                "high demand",
                "Quota exceeded",
                "RATE_LIMIT_EXCEEDED",
                "All providers failed",
            )
        ):
            raise AnalyzeRateLimitError() from exc
        raise
    total_roles = len(chunks)
    common_metadata = to_requirement_data(extract_common_metadata(raw_jd_clean))

    # Universal Email Header Extraction for robust multi-client recipient resolution
    universal_headers = extract_universal_email_headers(raw_jd_clean)
    if universal_headers.has_headers:
        if universal_headers.from_contacts and (
            common_metadata.client_lead_poc_from == NOT_SPECIFIED
            or not common_metadata.client_lead_poc_from
        ):
            c_from = universal_headers.from_contacts[0]
            common_metadata.client_lead_poc_from = (
                f"{c_from.name} <{c_from.email}>" if c_from.name else c_from.email
            )
            if common_metadata.requirement_from == NOT_SPECIFIED:
                common_metadata.requirement_from = company_from_email(c_from.email)

        if universal_headers.to_contacts and (
            common_metadata.internal_poc_to == NOT_SPECIFIED
            or not common_metadata.internal_poc_to
        ):
            common_metadata.internal_poc_to = ", ".join(
                [f"{c.name} <{c.email}>" if c.name else c.email for c in universal_headers.to_contacts]
            )

        if universal_headers.cc_contacts:
            common_metadata.client_poc_from_cc = ", ".join(
                [f"{c.name} <{c.email}>" if c.name else c.email for c in universal_headers.cc_contacts]
            )
        elif universal_headers.has_headers:
            # Independent missing field handling: do not contaminate CC with From address
            common_metadata.client_poc_from_cc = NOT_SPECIFIED

        if universal_headers.date and (
            common_metadata.demand_received_date == NOT_SPECIFIED
            or not common_metadata.demand_received_date
        ):
            common_metadata.demand_received_date = universal_headers.date

    # 3. Process each chunk in parallel
    async def process_chunk(index: int, chunk: RequirementChunk) -> AnalyzedRequirement:
        role_index = index + 1
        chunk_content = chunk.get("content", raw_jd_clean)
        chunk_title = chunk.get("title", "Single Requirement")
        if (
            universal_headers.subject
            and (not chunk_title or chunk_title == "Single Requirement" or is_generic_job_title(chunk_title))
        ):
            chunk_title = universal_headers.subject

        res = await extract_job_requirement(
            chunk_content,
            ExtractOptions(hint_title=chunk_title, full_jd_text=raw_jd_clean),
            llm_client=llm_client,
        )
        data, source = res.data, res.source

        # Merge common metadata
        merged = merge_inherited_fields(data, common_metadata)

        # Authoritative Universal Email Header Enforcement:
        # Prevents LLM hallucinations or model-side To/CC field swapping.
        if universal_headers.has_headers:
            if universal_headers.from_contacts:
                c_from = universal_headers.from_contacts[0]
                merged.client_lead_poc_from = (
                    f"{c_from.name} <{c_from.email}>" if c_from.name else c_from.email
                )
                if merged.requirement_from == NOT_SPECIFIED:
                    merged.requirement_from = company_from_email(c_from.email)
            if universal_headers.to_contacts:
                merged.internal_poc_to = ", ".join(
                    [f"{c.name} <{c.email}>" if c.name else c.email for c in universal_headers.to_contacts]
                )
            if universal_headers.cc_contacts:
                merged.client_poc_from_cc = ", ".join(
                    [f"{c.name} <{c.email}>" if c.name else c.email for c in universal_headers.cc_contacts]
                )
            else:
                merged.client_poc_from_cc = NOT_SPECIFIED

            if universal_headers.date and merged.demand_received_date == NOT_SPECIFIED:
                merged.demand_received_date = universal_headers.date

        if chunk_title and merged.job_title == NOT_SPECIFIED:
            merged.job_title = chunk_title

        num_pos = chunk.get("numberOfPositions")
        if merged.number_of_positions == NOT_SPECIFIED and num_pos:
            merged.number_of_positions = num_pos

        # Check for prior human correction overlay for this 1-based roleIndex
        correction = prior_corrections.get(role_index)
        correction_applied = False
        if correction:
            logger.info(f"[RL overlay] Applying correction for role {role_index}")
            overlaid_dict = apply_correction_overlay(merged, correction)
            merged = to_requirement_data(overlaid_dict)
            correction_applied = True

        return AnalyzedRequirement(
            **merged.model_dump(),
            requirement_title=chunk_title,
            role_index=role_index,
            total_roles=total_roles,
            extraction_source=source,
            correction_applied=correction_applied,
            policy_version=policy_version,
            email_headers=universal_headers.to_dict() if universal_headers.has_headers else None,
        )

    try:
        results = await asyncio.gather(*[process_chunk(i, c) for i, c in enumerate(chunks)])
    except AnalyzeRateLimitError:
        raise
    except Exception as exc:
        msg = str(exc)
        if any(
            term in msg
            for term in (
                "RATE_LIMIT_EXCEEDED",
                "Quota exceeded",
                "429",
                "503",
                "high demand",
                "rate limit",
                "All providers failed",
            )
        ):
            raise AnalyzeRateLimitError() from exc
        raise AnalyzeServiceError(msg) from exc

    persisted_info = None
    if session is not None:
        model_used = next((r.extraction_source for r in results if r.extraction_source), None)
        latency_ms = int((time.time() - started_at) * 1000)
        roles_payload = [
            AnalysisRolePayload(
                role_index=res.role_index,
                chunk_title=chunks[i].get("title") or res.requirement_title,
                chunk_content=chunks[i].get("content"),
                predicted=to_requirement_payload(res),
                extraction_source=res.extraction_source,
            )
            for i, res in enumerate(results)
        ]
        persisted_info = await save_analysis_run(
            session=session,
            raw_jd_text=raw_jd_clean,
            roles=roles_payload,
            model_used=model_used,
            latency_ms=latency_ms,
            policy_version=policy_version,
        )

    pol_ver = policy_version or settings.POLICY_VERSION
    requirements: List[AnalyzedRequirement] = []
    for index, res in enumerate(results):
        res.run_id = persisted_info.get("runId") if persisted_info else None
        res.prediction_id = (
            persisted_info.get("predictionIds")[index]
            if persisted_info
            and persisted_info.get("predictionIds")
            and index < len(persisted_info["predictionIds"])
            else None
        )
        res.policy_version = pol_ver
        requirements.append(res)

    return AnalyzeResponse(
        total_requirements=len(requirements),
        requirements=requirements,
        persisted=bool(persisted_info),
    )
