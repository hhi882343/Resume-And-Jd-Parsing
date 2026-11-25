import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
import regex as re

from src.extractResumeText import extract_plain_text_from_resume_buffer
from src.parseCoreResumeFields import (
    parse_core_fields_from_resume_text,
    extract_highest_qualification_from_any_text,
    extract_total_experience_info,
    extract_verbatim_designation,
    clean_and_validate_role_or_technologies,
    extract_current_location,
    extract_current_company,
)
from src.skillsExtractionEngine import (
    extract_skills_with_engine_sync,
    extract_skills_with_engine,
    validate_skills_against_section,
)
from src.resumeFieldSanitize import (
    is_certification_or_non_academic,
    clean_academic_specialization,
    compact_highest_qualification,
    sanitize_display_text,
)
from src.ai.extract import is_supported_file, extract_file_content
from src.ai.gemini import parse_resume_from_pdf, parse_resume_from_text, extract_skills_with_gemini
from src.ai.config import config
from src.jsRegex import js_trim, compile_re
from src.types import ParsedCandidateResume, BulkParseItemResult, MetaforgeParsed

logger = logging.getLogger(__name__)

ai_parsing_suspended: bool = False
ai_parsing_suspended_reason: Optional[str] = None


async def sleep(ms: float) -> None:
    await asyncio.sleep(ms / 1000.0)


def reset_ai_parsing_suspended() -> None:
    global ai_parsing_suspended, ai_parsing_suspended_reason
    ai_parsing_suspended = False
    ai_parsing_suspended_reason = None


def is_quota_or_rate_limit_error(err: Any) -> bool:
    msg = str(err)
    return bool(
        re.search(
            r'quota|rate.?limit|429|resource.?exhausted|too many requests|high demand|overloaded|503|unavailable|busy|invalid.*key|not found|not supported',
            msg,
            re.I,
        )
    )


def get_ai_parsing_suspended_reason() -> Optional[str]:
    return ai_parsing_suspended_reason


def is_metaforge_parser_available() -> bool:
    return bool(config.geminiApiKey)


def normalize_linkedin_url(raw: Optional[str]) -> Optional[str]:
    t = js_trim(raw or '')
    if not t:
        return None
    if re.search(r'^https?://', t, re.I):
        return t
    if re.search(r'^linkedin\.com', t, re.I) or re.search(r'^www\.linkedin\.com', t, re.I):
        clean = compile_re(r'^www\.', 'i').sub('', t)
        return f"https://{clean}"
    if re.search(r'^/in/', t, re.I):
        return f"https://www.linkedin.com{t}"
    if 'linkedin.com' in t:
        clean = compile_re(r'^https?://', 'i').sub('', t)
        return f"https://{clean}"
    return None


def join_list(items: Optional[List[str]]) -> Optional[str]:
    if not isinstance(items, list) or len(items) == 0:
        return None
    cleaned = [js_trim(s) for s in items if isinstance(s, str) and js_trim(s)]
    return ', '.join(cleaned) if cleaned else None


def map_metaforge_result(parsed: MetaforgeParsed, source_file: str) -> ParsedCandidateResume:
    skills = join_list(parsed.get('skills'))
    technology = join_list(parsed.get('technology'))
    role = clean_and_validate_role_or_technologies(parsed.get('role'))

    full_name = js_trim(parsed.get('full_name') or '') or None
    email = js_trim(parsed.get('email') or '') or None
    contact = js_trim(parsed.get('contact') or '') or None
    qualification = js_trim(parsed.get('qualification') or '') or None
    total_exp = js_trim(parsed.get('total_experience') or '') or None
    loc = js_trim(parsed.get('location') or parsed.get('current_location') or '') or None
    employer = js_trim(parsed.get('current_employer') or '') or None

    return {
        'candidateName': full_name,
        'email': email,
        'contactNumber': contact,
        'linkedinUrl': normalize_linkedin_url(parsed.get('linkedin')),
        'highestQualification': qualification,
        'skillsRaw': skills if skills is not None else technology,
        'technologiesRaw': role,
        'technologies': role,
        'totalExperience': total_exp,
        'relevantExperience': None,
        'currentEmployer': employer,
        'currentLocation': loc,
        'location': loc,
        'sourceFile': source_file,
        'parser': 'metaforge',
        'role': role,
    }


def map_legacy_result(
    parsed: Dict[str, Any],
    source_file: str,
) -> ParsedCandidateResume:
    role = clean_and_validate_role_or_technologies(parsed.get('role') or parsed.get('technologiesRaw'))
    return {
        'candidateName': parsed.get('candidateName'),
        'email': parsed.get('email'),
        'contactNumber': parsed.get('contactNumber'),
        'linkedinUrl': parsed.get('linkedinUrl'),
        'highestQualification': parsed.get('highestQualification'),
        'skillsRaw': parsed.get('skillsRaw') if parsed.get('skillsRaw') is not None else None,
        'technologiesRaw': role,
        'technologies': role,
        'totalExperience': parsed.get('totalExperienceText') or '',
        'relevantExperience': None,
        'currentEmployer': parsed.get('currentCompany'),
        'currentLocation': parsed.get('currentLocation') or None,
        'location': parsed.get('currentLocation') or None,
        'sourceFile': source_file,
        'parser': 'legacy',
        'role': role,
    }


def apply_evidence_lock(
    candidate: ParsedCandidateResume,
    raw_text: str,
) -> ParsedCandidateResume:
    norm_text = compile_re(r'\r?\n', 'g').sub(' ', raw_text)
    norm_text = compile_re(r'\s+', 'g').sub(' ', norm_text)
    norm_lower = norm_text.lower()

    def has_text_evidence(phrase: Optional[str]) -> bool:
        if not phrase:
            return False
        clean = js_trim(phrase).lower()
        if not clean:
            return False
        return clean in norm_lower

    # 1. QUALIFICATION
    qual: Optional[str] = js_trim(candidate.get('highestQualification') or '') or None
    if qual:
        if is_certification_or_non_academic(qual):
            qual = None
        else:
            qual = compact_highest_qualification(qual) or clean_academic_specialization(qual)
            if qual:
                words = [w for w in re.split(r'\s+', qual.lower()) if len(w) > 2]
                has_evidence = any(w in norm_lower for w in words)
                if not has_evidence:
                    qual = None

    if not qual and js_trim(raw_text):
        qual = extract_highest_qualification_from_any_text(raw_text)

    if qual:
        qual = clean_academic_specialization(qual) or compact_highest_qualification(qual) or qual
        if is_certification_or_non_academic(qual):
            qual = None

    # 2. TOTAL EXPERIENCE & RELEVANT EXPERIENCE
    exp_info = extract_total_experience_info(raw_text) if js_trim(raw_text) else {'text': '', 'years': None}
    final_total_exp: str = ''

    if exp_info.get('text') and js_trim(exp_info['text']):
        final_total_exp = js_trim(exp_info['text'])
    elif candidate.get('totalExperience') and js_trim(candidate['totalExperience']):
        candidate_exp = js_trim(candidate['totalExperience'])
        verified = extract_total_experience_info(candidate_exp)
        if verified.get('text') and js_trim(verified['text']):
            num_match = re.search(r'^(\d+(?:\.\d+)?\+?)', verified['text'])
            if num_match and num_match.group(1):
                num_escaped = num_match.group(1).replace('+', r'\+')
                in_text_re = compile_re(rf'\b{num_escaped}\s*(?:years?|yrs?|months?|mos?)', 'i')
                if in_text_re.search(raw_text):
                    final_total_exp = js_trim(verified['text'])

    final_relevant_exp = None

    # 3. SKILLS
    skills_engine_res = extract_skills_with_engine_sync(raw_text)
    final_skills_raw: Optional[str] = None

    if (
        skills_engine_res.get('diagnostics', {}).get('sectionDetected')
        and len(skills_engine_res.get('skills', [])) > 0
    ):
        final_skills_raw = ', '.join(skills_engine_res['skills'][:10])
    else:
        deterministic_fallback = skills_engine_res.get('skills', [])
        ai_tokens: List[str] = []
        if candidate.get('skillsRaw'):
            ai_tokens = [
                js_trim(s) for s in re.split(r'[,;\n|]', candidate['skillsRaw'] or '')
                if js_trim(s)
            ]

        valid_ai_res = validate_skills_against_section(ai_tokens, raw_text, 10)
        valid_ai_tokens = valid_ai_res.get('validSkills', [])
        combined = list(deterministic_fallback) + list(valid_ai_tokens)
        seen = set()
        deduped: List[str] = []
        for s in combined:
            k = s.lower()
            if k not in seen:
                seen.add(k)
                deduped.append(s)
                if len(deduped) >= 10:
                    break
        final_skills_raw = ', '.join(deduped) if deduped else None

    # 4. ROLE / DESIGNATION / DOMAIN / TECHNOLOGIES
    # Prevent later post-processing stages from overwriting a correctly extracted designation
    candidate_raw_role = js_trim(candidate.get('role') or '') or js_trim(candidate.get('technologiesRaw') or '') or None
    validated_candidate_role = clean_and_validate_role_or_technologies(candidate_raw_role) if candidate_raw_role else None

    role: Optional[str] = None
    if validated_candidate_role:
        role = validated_candidate_role
    else:
        verbatim_from_text = (
            clean_and_validate_role_or_technologies(
                extract_verbatim_designation(raw_text, candidate.get('currentEmployer'))
            )
            if js_trim(raw_text)
            else None
        )
        if verbatim_from_text:
            role = verbatim_from_text

    final_role = role or None

    # 5. LOCATION
    loc_candidate = js_trim(candidate.get('currentLocation') or '') or js_trim(candidate.get('location') or '') or None
    loc_from_text = extract_current_location(raw_text) if js_trim(raw_text) else None
    final_location = loc_candidate or loc_from_text or None

    res: ParsedCandidateResume = {
        **candidate,
        'highestQualification': sanitize_display_text(qual) if qual else None,
        'totalExperience': sanitize_display_text(final_total_exp) if final_total_exp else '',
        'relevantExperience': final_relevant_exp,
        'skillsRaw': final_skills_raw,
        'technologiesRaw': final_role,
        'technologies': final_role,
        'role': final_role,
        'currentEmployer': candidate.get('currentEmployer') or None,
        'currentLocation': sanitize_display_text(final_location) if final_location else None,
        'location': sanitize_display_text(final_location) if final_location else None,
    }
    return res


async def parse_resume_buffer_with_metaforge(
    buffer: bytes,
    filename: str,
) -> ParsedCandidateResume:
    if not is_supported_file(filename):
        raise RuntimeError("Unsupported file type. Supported: pdf, docx, doc, txt")

    extracted = await extract_file_content(buffer, filename)
    if extracted['type'] == 'pdf':
        parsed = await parse_resume_from_pdf(extracted['data'], buffer)
    else:
        parsed = await parse_resume_from_text(extracted['data'])

    plain_res = await extract_plain_text_from_resume_buffer(buffer, filename)
    raw_text = plain_res.get('text', '')
    text_for_evidence = raw_text or (extracted['data'] if extracted['type'] == 'text' else '')

    mapped = map_metaforge_result(parsed, filename)
    if not mapped.get('skillsRaw'):
        try:
            ai_skills_res = await extract_skills_with_engine(
                text_for_evidence,
                enable_ai_fallback=True,
                ai_fallback_fn=extract_skills_with_gemini,
            )
            if ai_skills_res.get('skillsRaw'):
                mapped['skillsRaw'] = ai_skills_res['skillsRaw']
        except Exception:
            pass

    return apply_evidence_lock(mapped, text_for_evidence)


async def parse_resume_buffer_legacy(
    buffer: bytes,
    filename: str,
) -> ParsedCandidateResume:
    plain_res = await extract_plain_text_from_resume_buffer(buffer, filename)
    text = plain_res.get('text', '')
    error = plain_res.get('error')
    if not js_trim(text):
        raise RuntimeError(error or 'Could not read text from this file.')

    parsed = parse_core_fields_from_resume_text(text)
    mapped = map_legacy_result(parsed, filename)
    return apply_evidence_lock(mapped, text)


async def parse_resume_buffer(
    buffer: bytes,
    filename: str,
) -> ParsedCandidateResume:
    global ai_parsing_suspended, ai_parsing_suspended_reason

    if is_metaforge_parser_available() and not ai_parsing_suspended:
        try:
            return await parse_resume_buffer_with_metaforge(buffer, filename)
        except Exception as err:
            if is_quota_or_rate_limit_error(err):
                ai_parsing_suspended = True
                ai_parsing_suspended_reason = (
                    "Gemini API quota or rate limit reached — using keyword parser for remaining resumes."
                )
                logger.warning(ai_parsing_suspended_reason)
            else:
                logger.warning(
                    f"Metaforge resume parse failed, falling back to keyword parser: {err}"
                )

    return await parse_resume_buffer_legacy(buffer, filename)


async def parse_resume_buffers_bulk(
    files: List[Dict[str, Any]],
) -> List[BulkParseItemResult]:
    results: List[BulkParseItemResult] = []

    for i, file_obj in enumerate(files):
        buffer: bytes = file_obj['buffer']
        filename: str = file_obj['filename']
        try:
            data = await parse_resume_buffer(buffer, filename)
            results.append({'sourceFile': filename, 'status': 'done', 'data': data})
        except Exception as err:
            results.append({
                'sourceFile': filename,
                'status': 'error',
                'error': str(err) if str(err) else 'Failed to parse resume',
            })

        if i < len(files) - 1 and is_metaforge_parser_available() and not ai_parsing_suspended:
            await sleep(800)

    return results


# Parity aliases
applyEvidenceLock = apply_evidence_lock
parseResumeBufferLegacy = parse_resume_buffer_legacy
parseResumeBufferWithMetaforge = parse_resume_buffer_with_metaforge
parseResumeBuffer = parse_resume_buffer
parseResumeBuffersBulk = parse_resume_buffers_bulk
isMetaforgeParserAvailable = is_metaforge_parser_available
getAiParsingSuspendedReason = get_ai_parsing_suspended_reason

