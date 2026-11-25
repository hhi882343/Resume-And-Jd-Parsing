import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
import regex as re

from src.ai.config import config
from src.ai.prompt import EXTRACTION_PROMPT, build_text_prompt
from src.ai.schema import extract_json_from_text, validate_parsed_result
from src.ai.normalize import normalize_parsed_result
from src.ai.pdfText import extract_pdf_text
from src.jsRegex import js_trim
from src.types import MetaforgeParsed

logger = logging.getLogger(__name__)

GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta'


def get_models_to_try() -> List[str]:
    return [config.geminiModel] + [m for m in config.geminiFallbackModels if m != config.geminiModel]


def is_retryable_model_error(status: int, msg: str) -> bool:
    return (
        status == 429
        or status == 503
        or status == 404
        or bool(re.search(r'quota|rate.?limit|high demand|overloaded|unavailable|try again', msg, re.I))
        or bool(re.search(r'not found|not supported', msg, re.I))
    )


def extract_gemini_text(data: Any) -> str:
    candidates = data.get('candidates') if isinstance(data, dict) else None
    candidate = candidates[0] if (isinstance(candidates, list) and len(candidates) > 0) else None

    if not candidate:
        block = data.get('promptFeedback', {}).get('blockReason') if isinstance(data, dict) else None
        if block:
            raise RuntimeError(f"Request blocked: {block}")
        raise RuntimeError("Empty response from Gemini")

    finish_reason = candidate.get('finishReason')
    if finish_reason and finish_reason not in ('STOP', 'MAX_TOKENS'):
        logger.warning(f"Gemini finishReason: {finish_reason}")
        if finish_reason == 'SAFETY':
            raise RuntimeError("Content blocked by safety filter. Try a different file format.")

    content = candidate.get('content') or {}
    parts = content.get('parts') or []
    text = ''.join(p.get('text', '') for p in parts if isinstance(p, dict))
    text = js_trim(text)
    if not text:
        raise RuntimeError("Empty response from Gemini")
    return text


async def sleep(ms: float) -> None:
    await asyncio.sleep(ms / 1000.0)


async def call_gemini(
    parts: List[Any],
    max_retries: int = 2,
    max_output_tokens: int = 4096,
    system_instruction: Optional[str] = None,
    use_json_mode: bool = True,
) -> str:
    models = get_models_to_try()
    last_error: Optional[Exception] = None

    for model in models:
        url = f"{GEMINI_BASE}/models/{model}:generateContent"

        generation_config: Dict[str, Any] = {
            "temperature": 0.1,
            "maxOutputTokens": max_output_tokens,
        }
        if use_json_mode:
            generation_config["responseMimeType"] = "application/json"

        body: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }

        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=300.0, connect=10.0)) as client:
                    resp = await client.post(
                        url,
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": config.geminiApiKey,
                        },
                        content=json.dumps(body, separators=(',', ':'), ensure_ascii=False),
                    )

                try:
                    data = resp.json()
                except Exception:
                    data = {}

                if resp.status_code >= 400:
                    msg = (data.get("error") or {}).get("message") if isinstance(data, dict) else None
                    if not msg:
                        msg = f"Gemini API error ({resp.status_code})"

                    if (
                        resp.status_code in (400, 401, 403)
                        or re.search(r'API key not valid|invalid.*api.*key', msg, re.I)
                    ):
                        raise RuntimeError(f"Invalid Gemini API key: {msg}")

                    if resp.status_code == 429 or re.search(r'quota|resource.?exhausted', msg, re.I):
                        raise RuntimeError(f"Gemini API quota exceeded: {msg}")

                    if resp.status_code == 404 or re.search(r'not found|not supported', msg, re.I):
                        last_error = RuntimeError(msg)
                        break

                    if is_retryable_model_error(resp.status_code, msg) and attempt < max_retries - 1:
                        await sleep(2000 if re.search(r'high demand|overloaded', msg, re.I) else 1000)
                        continue

                    if re.search(r'high demand|overloaded', msg, re.I):
                        raise RuntimeError("AI models are busy right now. Please wait a moment and try again.")

                    raise RuntimeError(msg)

                return extract_gemini_text(data)

            except Exception as err:
                last_error = err
                msg = str(err)
                if (
                    attempt < max_retries - 1
                    and not re.search(r'invalid.*gemini|invalid.*key|quota|not found|not supported', msg, re.I)
                ):
                    await sleep(1500 * (attempt + 1))
                    continue

                if not is_retryable_model_error(0, msg) or model == models[-1]:
                    raise last_error
                break

    if last_error:
        raise last_error
    raise RuntimeError("Gemini API request failed")


def finalize_parse(raw: str) -> MetaforgeParsed:
    parsed = extract_json_from_text(raw)
    validation = validate_parsed_result(parsed)
    if not validation.get('valid'):
        err_strs = ', '.join(validation.get('errors', []))
        raise RuntimeError(f"Invalid parse result: {err_strs}")
    return normalize_parsed_result(parsed)


async def try_parse(parts: List[Any], label: str) -> MetaforgeParsed:
    errors: List[str] = []

    for use_json_mode in [True, False]:
        try:
            raw = await call_gemini(parts, max_output_tokens=4096, use_json_mode=use_json_mode)
            return finalize_parse(raw)
        except Exception as err:
            msg = str(err)
            errors.append(f"{label}{'' if use_json_mode else ' (plain)'}: {msg}")
            if not re.search(r'No JSON|Empty response|Invalid parse', msg, re.I):
                raise err

    raise RuntimeError(errors[-1] if errors else "Failed to parse resume")


async def parse_resume_from_pdf(base64_data: str, pdf_buffer: Optional[bytes] = None) -> MetaforgeParsed:
    pdf_parts = [
        {"inlineData": {"mimeType": "application/pdf", "data": base64_data}},
        {"text": EXTRACTION_PROMPT},
    ]
    try:
        return await try_parse(pdf_parts, "PDF")
    except Exception as pdf_err:
        if re.search(r'invalid.*key|quota|resource.?exhausted', str(pdf_err), re.I):
            raise pdf_err
        logger.warning(f"PDF multimodal parse failed, trying text fallback: {pdf_err}")

        if pdf_buffer:
            text = await extract_pdf_text(pdf_buffer)
            if len(text) > 50:
                try:
                    return await try_parse([{"text": build_text_prompt(text)}], "PDF-text")
                except Exception as text_err:
                    msg = str(text_err) or str(pdf_err)
                    raise RuntimeError(msg)

        raise RuntimeError(str(pdf_err) or "Failed to parse PDF resume")


async def parse_resume_from_text(resume_text: str) -> MetaforgeParsed:
    return await try_parse([{"text": build_text_prompt(resume_text)}], "text")


async def extract_skills_with_gemini(skills_section_text: str) -> List[str]:
    if not skills_section_text or not js_trim(skills_section_text):
        return []

    prompt = f"""You are a strict recruitment extraction specialist.
Extract ONLY the explicitly mentioned individual technical and professional skills from the provided text snippet.

RULES:
1. Extract ONLY individual skill names that literally appear or are clearly demonstrated in the text snippet.
2. PRIMARY: Extract from the dedicated Skills section if present.
3. FALLBACK: If no dedicated Skills section exists, extract explicitly evidenced skills from summary, technical projects, work experience, or education.
4. Separate multiple skills from compound lines or categories (e.g. "Languages: C++, Python" -> ["C++", "Python"]).
5. NEVER infer, guess, or invent skills not present in the text.
6. Do NOT extract whole sentences, job responsibilities, project descriptions, company names, or degree names.
7. Return at most 10 unique skills in order of appearance.
8. Return JSON format strictly:
{{
  "skills": ["Skill 1", "Skill 2"]
}}

SOURCE TEXT:
\"\"\"
{skills_section_text[:4000]}
\"\"\""""

    try:
        raw = await call_gemini([{"text": prompt}], max_output_tokens=1024, use_json_mode=True)
        parsed = extract_json_from_text(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("skills"), list):
            skills = [
                js_trim(s) for s in parsed["skills"]
                if isinstance(s, str) and js_trim(s)
            ]
            return skills[:10]
    except Exception as err:
        logger.warning(f"[skills-engine] AI fallback call failed: {err}")
    return []


async def chat_with_context(
    messages: List[Dict[str, Any]],
    candidate_profile: Optional[Any] = None,
) -> str:
    system_instruction = (
        "You are an expert technical recruiter and talent evaluation specialist."
        + (f"\nCandidate profile:\n{json.dumps(candidate_profile, indent=2)}" if candidate_profile else "")
        + "\nHelp assess candidates, evaluate skill alignment, compare with job descriptions, and highlight strengths or risks. Be concise, objective, and professional."
    )

    contents = [
        {
            "role": "model" if m.get("role") == "assistant" else "user",
            "parts": [{"text": m["content"] if isinstance(m.get("content"), str) else json.dumps(m.get("content"))}],
        }
        for m in messages
    ]

    models = get_models_to_try()
    last_error: Optional[Exception] = None

    for model in models:
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=300.0, connect=10.0)) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": config.geminiApiKey,
                    },
                    content=json.dumps({
                        "systemInstruction": {"parts": [{"text": system_instruction}]},
                        "contents": contents,
                        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1024},
                    }, separators=(',', ':'), ensure_ascii=False),
                )
            try:
                data = resp.json()
            except Exception:
                data = {}

            if resp.status_code >= 400:
                msg = (data.get("error") or {}).get("message") if isinstance(data, dict) else None
                if not msg:
                    msg = f"Gemini API error ({resp.status_code})"
                if is_retryable_model_error(resp.status_code, msg) and model != models[-1]:
                    last_error = RuntimeError(msg)
                    continue
                if re.search(r'quota|rate.?limit', msg, re.I):
                    raise RuntimeError("Gemini API quota exceeded. Check billing or try again later.")
                raise RuntimeError(msg)

            return extract_gemini_text(data)
        except Exception as err:
            last_error = err
            if model != models[-1]:
                continue
            raise

    if last_error:
        raise last_error
    raise RuntimeError("Chat request failed")


# Parity aliases
callGemini = call_gemini
tryParse = try_parse
parseResumeFromPdf = parse_resume_from_pdf
parseResumeFromText = parse_resume_from_text
extractSkillsWithGemini = extract_skills_with_gemini
chatWithContext = chat_with_context

