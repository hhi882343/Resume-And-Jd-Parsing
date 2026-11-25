"""FastAPI router for POST /api/corrections endpoint.

Ported directly from src/app/api/corrections/route.ts.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.response import JSJSONResponse
from app.db.session import get_db_session
from app.services.feedback import (
    save_correction_with_context,
    to_requirement_payload,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/corrections", response_class=JSJSONResponse)
async def corrections_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> JSJSONResponse:
    """Save recruiter corrections to database, compute reward scores, and create preference pairs."""
    try:
        raw_body = await request.body()
        try:
            body = json.loads(raw_body.decode("utf-8")) if raw_body else None
        except Exception as exc:
            return JSJSONResponse({"error": str(exc)}, status_code=500)

        raw_jd_text = ""
        predicted = None
        corrected = None

        if isinstance(body, dict):
            raw_val = body.get("rawJdText")
            if raw_val is not None:
                if not isinstance(raw_val, str):
                    raise TypeError("body?.rawJdText?.trim is not a function")
                raw_jd_text = raw_val.strip()
            predicted = body.get("predicted")
            corrected = body.get("corrected")

        if (
            not raw_jd_text
            or not predicted
            or not corrected
            or not isinstance(predicted, dict)
            or not isinstance(corrected, dict)
        ):
            return JSJSONResponse(
                {"error": "rawJdText, predicted, and corrected data are required"},
                status_code=400,
            )

        if (
            not isinstance(corrected.get("jobTitle"), str)
            or not isinstance(corrected.get("mandatorySkills"), list)
            or not isinstance(corrected.get("skills"), list)
        ):
            return JSJSONResponse(
                {"error": "Invalid corrected data shape: missing required fields"},
                status_code=400,
            )

        role_index = predicted.get("roleIndex") if predicted.get("roleIndex") is not None else 1
        total_roles = predicted.get("totalRoles") if predicted.get("totalRoles") is not None else 1

        result = await save_correction_with_context(
            session=session,
            raw_jd_text=raw_jd_text,
            chunk_title=predicted.get("requirementTitle"),
            role_index=role_index,
            total_roles=total_roles,
            model_used=predicted.get("extractionSource"),
            predicted=to_requirement_payload(predicted),
            corrected=to_requirement_payload(corrected),
            prediction_id=predicted.get("predictionId"),
            run_id=predicted.get("runId"),
        )

        if not result["saved"]:
            return JSJSONResponse(
                {
                    "success": True,
                    "saved": False,
                    "rewardScore": result["rewardScore"],
                    "fieldRewards": result["fieldRewards"],
                    "preferencePairCreated": False,
                    "message": "No field changes vs AI output — run marked accepted; no new training pair.",
                }
            )

        return JSJSONResponse(
            {
                "success": True,
                **result,
                "message": "Correction saved to learning database as RL preference pair for future training.",
            }
        )

    except Exception as exc:
        msg = str(exc) or "Failed to save correction"
        return JSJSONResponse({"error": msg}, status_code=500)
