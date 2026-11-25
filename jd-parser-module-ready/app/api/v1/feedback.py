"""FastAPI router for GET /api/feedback/stats endpoint.

Ported directly from src/app/api/feedback/stats/route.ts.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.response import JSJSONResponse
from app.db.session import get_db_session
from app.services.feedback import get_feedback_stats

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/feedback/stats", response_class=JSJSONResponse)
async def feedback_stats_endpoint(
    session: AsyncSession = Depends(get_db_session),
) -> JSJSONResponse:
    """Load aggregate counts, average reward score, and DPO training readiness."""
    try:
        stats = await get_feedback_stats(session)
        return JSJSONResponse(stats)
    except Exception as exc:
        msg = str(exc) or "Failed to load feedback stats"
        return JSJSONResponse({"error": msg}, status_code=500)
