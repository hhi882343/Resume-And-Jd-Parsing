"""FastAPI router for POST /api/analyze endpoint.

Ported directly from src/app/api/analyze/route.ts.
Preserves exact body parsing, status codes, error payloads, and JSON response formats.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.response import JSJSONResponse
from app.db.session import get_db_session
from app.services.extraction import (
    AnalyzeRateLimitError,
    orchestrate_analysis,
)
from app.services.llm_client import BaseLLMClient, CascadeLLMClient
from app.services.prompts import RATE_LIMIT_MESSAGE

logger = logging.getLogger(__name__)

router = APIRouter()


def get_llm_client(request: Request) -> Optional[BaseLLMClient]:
    """Dependency for providing optional injected or mock LLM client."""
    return getattr(request.app.state, "llm_client", None)


@router.post("/api/analyze", response_class=JSJSONResponse)
async def analyze_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    llm_client: Optional[BaseLLMClient] = Depends(get_llm_client),
) -> JSJSONResponse:
    """Analyze raw job description text into structured ATS requirement records."""
    try:
        raw_body = await request.body()
        try:
            body = json.loads(raw_body.decode("utf-8")) if raw_body else None
        except Exception as exc:
            # Match Next.js request.json() SyntaxError caught in catch block
            return JSJSONResponse({"error": str(exc)}, status_code=500)

        raw_jd_text = ""
        if isinstance(body, dict):
            raw_val = body.get("rawJdText")
            if raw_val is not None:
                if not isinstance(raw_val, str):
                    raise TypeError("body?.rawJdText?.trim is not a function")
                raw_jd_text = raw_val.strip()

        if not raw_jd_text:
            return JSJSONResponse(
                {"error": "Job description text is required"},
                status_code=400,
            )

        client = llm_client or CascadeLLMClient()
        response = await orchestrate_analysis(
            raw_jd_text=raw_jd_text,
            session=session,
            llm_client=client,
        )
        dumped = response.model_dump(by_alias=True)
        if isinstance(dumped, dict):
            for req in dumped.get("requirements", []):
                req.pop("lastRewardScore", None)
                req.pop("feedbackSaved", None)
        return JSJSONResponse(dumped)

    except AnalyzeRateLimitError as err:
        return JSJSONResponse(
            {
                "error": "API rate limit exceeded. The system is retrying with alternative providers. Please try again in a few moments.",
                "details": err.details,
                "isRateLimit": True,
            },
            status_code=429,
        )
    except Exception as exc:
        msg = str(exc)
        is_rate_limit = any(
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
        )
        if is_rate_limit:
            return JSJSONResponse(
                {
                    "error": "API rate limit exceeded. The system is retrying with alternative providers. Please try again in a few moments.",
                    "details": RATE_LIMIT_MESSAGE,
                    "isRateLimit": True,
                },
                status_code=429,
            )
        return JSJSONResponse(
            {"error": msg or "Failed to analyze job description"},
            status_code=500,
        )
