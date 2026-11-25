"""Feedback, correction, and DPO training data service.

Ported directly from:
- src/lib/feedback-store.ts
- src/lib/requirement-serialize.ts
- scripts/export-dpo-dataset.ts
"""

from __future__ import annotations

import json
import logging
import math
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.normalize import to_requirement_data
from app.core.reward import compute_reward, has_meaningful_diff, js_json_stringify
from app.models.correction import Correction
from app.models.policy_version import PolicyVersion
from app.models.prediction import AnalysisPrediction
from app.models.preference_pair import PreferencePair
from app.models.run import AnalysisRun
from app.schemas.requirement import NOT_SPECIFIED, RequirementData

logger = logging.getLogger(__name__)

EMPTY_REQUIREMENT_PAYLOAD: Dict[str, Any] = {
    "requirementId": NOT_SPECIFIED,
    "jobTitle": NOT_SPECIFIED,
    "clientLeadPocFrom": NOT_SPECIFIED,
    "clientPocFromCc": NOT_SPECIFIED,
    "internalPocTo": NOT_SPECIFIED,
    "requirementFrom": NOT_SPECIFIED,
    "demandReceivedDate": NOT_SPECIFIED,
    "closedDate": NOT_SPECIFIED,
    "openSince": NOT_SPECIFIED,
    "typeOfDemand": NOT_SPECIFIED,
    "jobStatus": "Unassigned",
    "priority": NOT_SPECIFIED,
    "relevantExperience": NOT_SPECIFIED,
    "overallExperience": NOT_SPECIFIED,
    "qualificationCriteria": NOT_SPECIFIED,
    "employmentType": NOT_SPECIFIED,
    "workMode": NOT_SPECIFIED,
    "workTimings": NOT_SPECIFIED,
    "location": NOT_SPECIFIED,
    "numberOfPositions": NOT_SPECIFIED,
    "budgetCurrency": NOT_SPECIFIED,
    "monthlyBudget": NOT_SPECIFIED,
    "annualBudget": NOT_SPECIFIED,
    "noticePeriod": NOT_SPECIFIED,
    "sla": NOT_SPECIFIED,
    "mandatorySkills": [],
    "skills": [],
    "jobDescription": "",
}


def to_requirement_payload(data: Any) -> Dict[str, Any]:
    """Strip API/UI metadata before reward comparison or DB storage matching TS toRequirementPayload."""
    payload = dict(EMPTY_REQUIREMENT_PAYLOAD)

    if isinstance(data, dict):
        for key in EMPTY_REQUIREMENT_PAYLOAD:
            if key in data:
                payload[key] = data[key]
            else:
                # Check snake_case variant
                import re

                snake = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()
                if snake in data:
                    payload[key] = data[snake]
    elif hasattr(data, "model_dump"):
        dumped = data.model_dump(by_alias=True)
        for key in EMPTY_REQUIREMENT_PAYLOAD:
            if key in dumped:
                payload[key] = dumped[key]
    else:
        for key in EMPTY_REQUIREMENT_PAYLOAD:
            val = getattr(data, key, None)
            if val is not None:
                payload[key] = val
            else:
                import re

                snake = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()
                val_snake = getattr(data, snake, None)
                if val_snake is not None:
                    payload[key] = val_snake

    return payload


@dataclass
class AnalysisRolePayload:
    """Per-role payload for persisting an analysis run matching TypeScript AnalysisRolePayload."""

    role_index: int
    predicted: Any
    chunk_title: Optional[str] = None
    chunk_content: Optional[str] = None
    extraction_source: Optional[str] = None


async def save_analysis_run(
    session: AsyncSession,
    raw_jd_text: str,
    roles: List[AnalysisRolePayload],
    model_used: Optional[str] = None,
    latency_ms: Optional[int] = None,
    policy_version: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Persist every analyze run + per-role predictions (best-effort, returns None on failure)."""
    if len(roles) == 0:
        return None

    pol_ver = policy_version or os.getenv("POLICY_VERSION") or settings.POLICY_VERSION

    try:
        run = AnalysisRun(
            id=str(uuid.uuid4()),
            raw_jd_text=raw_jd_text,
            model_used=model_used,
            policy_version=pol_ver,
            chunk_count=len(roles),
            latency_ms=latency_ms,
            status="success",
        )
        session.add(run)
        await session.flush()

        predictions: List[AnalysisPrediction] = []
        for role in roles:
            payload = to_requirement_payload(role.predicted)
            pred = AnalysisPrediction(
                id=str(uuid.uuid4()),
                run_id=run.id,
                role_index=role.role_index,
                chunk_title=role.chunk_title,
                chunk_content=role.chunk_content,
                predicted_json=js_json_stringify(payload),
            )
            session.add(pred)
            predictions.append(pred)

        await session.flush()

        # PolicyVersion upsert
        pv_stmt = select(PolicyVersion).where(PolicyVersion.version == pol_ver)
        pv_res = await session.execute(pv_stmt)
        existing_pv = pv_res.scalar_one_or_none()
        if not existing_pv:
            new_pv = PolicyVersion(
                id=str(uuid.uuid4()),
                version=pol_ver,
                base_model="unknown" if model_used is None else model_used,
            )
            session.add(new_pv)

        await session.commit()

        return {
            "runId": run.id,
            "predictionIds": [p.id for p in predictions],
        }
    except Exception as exc:
        logger.error(f"Failed to persist analysis run: {exc}", exc_info=True)
        await session.rollback()
        return None


def _validate_prisma_int(val: Any, field_name: str) -> int | float:
    if isinstance(val, bool):
        raise TypeError(f"Provided Boolean, expected Int for {field_name}")
    if isinstance(val, int):
        if val < -2147483648 or val > 2147483647:
            raise ValueError(
                f"Unable to fit integer value {val} into a 32-bit signed integer for {field_name}"
            )
        return val
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val) or val < -2147483648 or val > 2147483647:
            raise ValueError(
                f"Unable to fit float value {val} into a 32-bit signed integer for {field_name}"
            )
        return val
    raise TypeError(f"Provided {type(val).__name__}, expected Int for {field_name}")


async def save_correction_with_context(
    session: AsyncSession,
    raw_jd_text: str,
    role_index: int,
    total_roles: int,
    predicted: Any,
    corrected: Any,
    chunk_title: Optional[str] = None,
    chunk_content: Optional[str] = None,
    model_used: Optional[str] = None,
    prediction_id: Optional[str] = None,
    run_id: Optional[str] = None,
    policy_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Links a recruiter correction to an existing prediction when possible.

    Creates a DPO preference pair only when the edit differs from model output (score < 0.98).
    """
    if role_index is not None:
        role_index = _validate_prisma_int(role_index, "roleIndex")
    if total_roles is not None:
        total_roles = _validate_prisma_int(total_roles, "totalRoles")

    predicted_payload = to_requirement_payload(predicted)
    corrected_payload = to_requirement_payload(corrected)
    reward_result = compute_reward(predicted_payload, corrected_payload)
    score: float = reward_result["score"]
    field_rewards: Dict[str, float] = reward_result["field_rewards"]
    pol_ver = policy_version or os.getenv("POLICY_VERSION") or settings.POLICY_VERSION

    if not has_meaningful_diff(predicted_payload, corrected_payload):
        if run_id:
            try:
                run_stmt = select(AnalysisRun).where(AnalysisRun.id == run_id)
                run_res = await session.execute(run_stmt)
                run_obj = run_res.scalar_one_or_none()
                if run_obj:
                    run_obj.status = "accepted"
                    await session.commit()
            except Exception as exc:
                logger.warning(f"Failed to mark run accepted: {exc}")
                await session.rollback()

        return {
            "saved": False,
            "rewardScore": score,
            "fieldRewards": field_rewards,
            "preferencePairCreated": False,
            "runId": run_id,
            "predictionId": prediction_id,
        }

    try:
        if prediction_id:
            pred_stmt = select(AnalysisPrediction).where(AnalysisPrediction.id == prediction_id)
            pred_res = await session.execute(pred_stmt)
            prediction = pred_res.scalar_one_or_none()
            if not prediction:
                raise ValueError(f"AnalysisPrediction not found: {prediction_id}")

            correction = Correction(
                id=str(uuid.uuid4()),
                prediction_id=prediction.id,
                corrected_json=js_json_stringify(corrected_payload),
                reward_score=score,
                field_rewards=js_json_stringify(field_rewards),
            )
            session.add(correction)
            await session.flush()

            pref_pair = PreferencePair(
                id=str(uuid.uuid4()),
                prediction_id=prediction.id,
                correction_id=correction.id,
                rejected_json=js_json_stringify(predicted_payload),
                chosen_json=js_json_stringify(corrected_payload),
                reward_score=score,
            )
            session.add(pref_pair)

            if run_id:
                run_stmt = select(AnalysisRun).where(AnalysisRun.id == run_id)
                run_res = await session.execute(run_stmt)
                run_obj = run_res.scalar_one_or_none()
                if not run_obj:
                    raise ValueError(f"AnalysisRun not found: {run_id}")
                run_obj.status = "corrected"
            elif prediction.run_id:
                run_stmt = select(AnalysisRun).where(AnalysisRun.id == prediction.run_id)
                run_res = await session.execute(run_stmt)
                run_obj = run_res.scalar_one_or_none()
                if run_obj:
                    run_obj.status = "corrected"

            ret_run_id = prediction.run_id if run_id is None else run_id
            ret_pred_id = prediction.id
            ret_corr_id = correction.id
        else:
            run = AnalysisRun(
                id=str(uuid.uuid4()),
                raw_jd_text=raw_jd_text,
                model_used=model_used,
                policy_version=pol_ver,
                chunk_count=total_roles,
                status="corrected",
            )
            session.add(run)
            await session.flush()

            prediction = AnalysisPrediction(
                id=str(uuid.uuid4()),
                run_id=run.id,
                role_index=role_index,
                chunk_title=chunk_title,
                chunk_content=chunk_content,
                predicted_json=js_json_stringify(predicted_payload),
            )
            session.add(prediction)
            await session.flush()

            correction = Correction(
                id=str(uuid.uuid4()),
                prediction_id=prediction.id,
                corrected_json=js_json_stringify(corrected_payload),
                reward_score=score,
                field_rewards=js_json_stringify(field_rewards),
            )
            session.add(correction)
            await session.flush()

            pref_pair = PreferencePair(
                id=str(uuid.uuid4()),
                prediction_id=prediction.id,
                correction_id=correction.id,
                rejected_json=js_json_stringify(predicted_payload),
                chosen_json=js_json_stringify(corrected_payload),
                reward_score=score,
            )
            session.add(pref_pair)

            ret_run_id = run.id
            ret_pred_id = prediction.id
            ret_corr_id = correction.id

        # Upsert PolicyVersion
        pv_stmt = select(PolicyVersion).where(PolicyVersion.version == pol_ver)
        pv_res = await session.execute(pv_stmt)
        existing_pv = pv_res.scalar_one_or_none()
        if not existing_pv:
            new_pv = PolicyVersion(
                id=str(uuid.uuid4()),
                version=pol_ver,
                base_model="unknown" if model_used is None else model_used,
            )
            session.add(new_pv)

        await session.commit()

        return {
            "saved": True,
            "runId": ret_run_id,
            "predictionId": ret_pred_id,
            "correctionId": ret_corr_id,
            "rewardScore": score,
            "fieldRewards": field_rewards,
            "preferencePairCreated": True,
        }
    except Exception as exc:
        logger.error(f"Failed to save correction with context: {exc}", exc_info=True)
        await session.rollback()
        raise


async def get_latest_corrections_for_jd(
    session: AsyncSession,
    raw_jd_text: str,
) -> Dict[int, RequirementData]:
    """Look up the most recent human corrections for a given raw JD text.

    Returns a map of roleIndex (1-based) -> corrected RequirementData.
    """
    try:
        stmt = (
            select(AnalysisRun)
            .where(
                AnalysisRun.raw_jd_text == raw_jd_text,
                AnalysisRun.status.in_(["corrected", "accepted"]),
            )
            .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
            .limit(5)
            .options(
                selectinload(AnalysisRun.predictions).selectinload(AnalysisPrediction.corrections)
            )
        )
        res = await session.execute(stmt)
        runs = res.scalars().all()

        correction_map: Dict[int, RequirementData] = {}

        for run in runs:
            for prediction in run.predictions:
                sorted_corrections = sorted(
                    prediction.corrections,
                    key=lambda c: c.corrected_at,
                    reverse=True,
                )
                if not sorted_corrections:
                    continue

                latest_corr = sorted_corrections[0]
                role_index = prediction.role_index
                if role_index in correction_map:
                    continue

                try:
                    corrected_raw = json.loads(latest_corr.corrected_json)
                    correction_map[role_index] = to_requirement_data(corrected_raw)
                except Exception:
                    # skip malformed JSON
                    pass

        return correction_map
    except Exception as exc:
        logger.error(f"Failed to look up corrections: {exc}", exc_info=True)
        return {}


async def get_feedback_stats(session: AsyncSession) -> Dict[str, Any]:
    """Compute aggregate counts, average reward score, and DPO readiness."""
    runs = (await session.execute(select(func.count(AnalysisRun.id)))).scalar_one()
    predictions = (await session.execute(select(func.count(AnalysisPrediction.id)))).scalar_one()
    corrections = (await session.execute(select(func.count(Correction.id)))).scalar_one()
    pairs = (await session.execute(select(func.count(PreferencePair.id)))).scalar_one()

    avg_stmt = select(func.avg(Correction.reward_score)).where(Correction.reward_score < 0.999)
    avg_reward = (await session.execute(avg_stmt)).scalar_one_or_none()

    return {
        "totalAnalysisRuns": runs,
        "totalPredictions": predictions,
        "totalCorrections": corrections,
        "totalPreferencePairs": pairs,
        "avgReward": float(avg_reward) if avg_reward is not None else None,
        "policyVersion": os.getenv("POLICY_VERSION") or settings.POLICY_VERSION,
        "dpoReady": pairs >= 50,
    }


async def export_dpo(
    session: AsyncSession,
    output_path: Optional[str] = None,
) -> str:
    """Export preference pairs ordered by created_at ascending in JSONL format."""
    stmt = (
        select(PreferencePair)
        .order_by(PreferencePair.created_at.asc(), PreferencePair.id.asc())
        .options(selectinload(PreferencePair.prediction).selectinload(AnalysisPrediction.run))
    )
    res = await session.execute(stmt)
    pairs = res.scalars().all()

    lines: List[str] = []
    for pair in pairs:
        chunk_text = (
            pair.prediction.chunk_content
            if pair.prediction.chunk_content is not None
            else pair.prediction.run.raw_jd_text
        )
        item = {
            "prompt": f"Extract structured requirement data from this JD:\n\n{chunk_text}",
            "rejected": pair.rejected_json,
            "chosen": pair.chosen_json,
            "reward_score": pair.reward_score,
            "prediction_id": pair.prediction_id,
        }
        lines.append(js_json_stringify(item))

    jsonl = "\n".join(lines)
    if jsonl:
        jsonl += "\n"

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(jsonl, encoding="utf-8")

    return jsonl
