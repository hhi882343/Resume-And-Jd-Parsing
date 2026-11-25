"""FastAPI router for Universal Email Header Extraction endpoints."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request

from app.api.response import JSJSONResponse
from app.core.email_extractor import extract_email_headers_data

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/extract-email-headers", response_class=JSJSONResponse)
@router.post("/api/email/headers", response_class=JSJSONResponse)
async def extract_headers_endpoint(request: Request) -> JSJSONResponse:
    """Extract From, To, CC, Subject, and Date fields from raw pasted email content.

    Returns the exact JSON contract schema:
    {
      "from": [{"name": "John Smith", "email": "john@company.com"}],
      "to": [{"name": "Recruitment Team", "email": "hr@company.com"}],
      "cc": [{"name": "Hiring Manager", "email": "manager@company.com"}]
    }
    """
    raw_text = ""
    try:
        raw_body = await request.body()
        if raw_body:
            try:
                body = json.loads(raw_body.decode("utf-8"))
                if isinstance(body, dict):
                    raw_text = str(
                        body.get("rawText")
                        or body.get("raw_text")
                        or body.get("rawJdText")
                        or body.get("text")
                        or ""
                    )
                elif isinstance(body, str):
                    raw_text = body
            except Exception:
                raw_text = raw_body.decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.warning(f"Failed to read request body: {exc}")

    if not raw_text.strip():
        return JSJSONResponse({"from": [], "to": [], "cc": []}, status_code=200)

    headers_data = extract_email_headers_data(raw_text, include_metadata=True)
    return JSJSONResponse(headers_data, status_code=200)
