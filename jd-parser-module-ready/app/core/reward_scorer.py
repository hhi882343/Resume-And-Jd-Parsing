"""Pure-Python reward scoring engine ported directly from TypeScript src/lib/reward.ts.

Calculates field-weighted reward scores and F1 skill scores for RL feedback
and DPO preference pair generation.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, Sequence

if TYPE_CHECKING:
    from app.schemas.requirement import RequirementData

NOT_SPECIFIED = "Not specified"

FIELD_WEIGHTS: Dict[str, float] = {
    "jobTitle": 2.0,
    "location": 1.5,
    "numberOfPositions": 1.5,
    "annualBudget": 1.5,
    "monthlyBudget": 1.0,
    "workMode": 1.0,
    "workTimings": 1.0,
    "overallExperience": 1.0,
    "clientLeadPocFrom": 1.0,
    "internalPocTo": 1.0,
    "requirementFrom": 1.0,
    "demandReceivedDate": 1.0,
    "mandatorySkills": 2.0,
    "skills": 1.0,
    "employmentType": 0.8,
    "priority": 0.8,
    "qualificationCriteria": 0.8,
    "noticePeriod": 0.8,
    "budgetCurrency": 0.5,
    "typeOfDemand": 0.5,
    "relevantExperience": 0.5,
    "clientPocFromCc": 0.5,
    "sla": 0.3,
    "jobStatus": 0.3,
    "closedDate": 0.3,
    "openSince": 0.2,
    "jobDescription": 0.2,
}

SCORED_FIELDS = list(FIELD_WEIGHTS.keys())


def normalize_string(value: str) -> str:
    """Normalize string by trimming, lowercasing, and collapsing whitespace."""
    return re.sub(r"\s+", " ", value.strip().lower())


def score_string(predicted: str, corrected: str) -> float:
    """Calculate overlap reward score for single-string fields."""
    p = normalize_string(predicted)
    c = normalize_string(corrected)
    if p == c:
        return 1.0
    if p == NOT_SPECIFIED.lower() and c != NOT_SPECIFIED.lower():
        return 0.0

    # Partial credit only when strings significantly overlap by length
    if p in c or c in p:
        shorter = min(len(p), len(c))
        longer = max(len(p), len(c))
        if longer == 0:
            return 1.0
        # >= 50% overlap -> 0.8 credit; otherwise 0.3 (some signal but not great)
        return 0.8 if (shorter / longer) >= 0.5 else 0.3

    return 0.0


def score_skills(predicted: Sequence[str], corrected: Sequence[str]) -> float:
    """Calculate F1 overlap score between predicted and corrected skill lists."""
    # User cleared all skills the model predicted -> model was completely wrong
    if not corrected and predicted:
        return 0.0
    # Both empty -> correct
    if not corrected and not predicted:
        return 1.0
    # Model predicted nothing but user added skills -> model missed everything
    if not predicted:
        return 0.0

    pred_set = {normalize_string(s) for s in predicted}
    corr_set = {normalize_string(s) for s in corrected}

    hits = sum(1 for skill in corr_set if skill in pred_set)
    precision = hits / len(pred_set)
    recall = hits / len(corr_set)

    if precision + recall == 0.0:
        return 0.0
    return (2.0 * precision * recall) / (precision + recall)


def _get_field_value(data: Any, field_name: str) -> Any:
    """Extract field value from either RequirementData model or dict."""
    if isinstance(data, dict):
        if field_name in data:
            return data[field_name]
        # Check snake_case fallback
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", field_name).lower()
        return data.get(snake)
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", field_name).lower()
    return getattr(data, snake, getattr(data, field_name, None))


def compute_reward(predicted: Any, corrected: Any) -> Dict[str, Any]:
    """Calculate field-level and composite reward score between predicted and corrected requirements.

    Composite score is clamped to [0.0, 1.0] with NO rounding in calculation.
    """
    field_rewards: Dict[str, float] = {}
    weighted_sum = 0.0
    total_weight = 0.0

    for field in SCORED_FIELDS:
        weight = FIELD_WEIGHTS[field]
        reward: float

        p_val = _get_field_value(predicted, field)
        c_val = _get_field_value(corrected, field)

        if field in ("mandatorySkills", "skills"):
            p_skills = list(p_val) if p_val and isinstance(p_val, (list, tuple)) else []
            c_skills = list(c_val) if c_val and isinstance(c_val, (list, tuple)) else []
            reward = score_skills(p_skills, c_skills)
        else:
            p_str = "" if p_val is None else str(p_val)
            c_str = "" if c_val is None else str(c_val)
            reward = score_string(p_str, c_str)

        field_rewards[field] = reward
        weighted_sum += reward * weight
        total_weight += weight

    raw_score = weighted_sum / total_weight if total_weight > 0.0 else 1.0
    # Phase 4 Requirement: clamp only, NO rounding. Parity tests assert pytest.approx(abs=1e-9)
    clamped_score = max(0.0, min(1.0, raw_score))

    return {
        "score": clamped_score,
        "field_rewards": field_rewards,
    }


def has_meaningful_diff(predicted: Any, corrected: Any) -> bool:
    """Check if correction differs from prediction beyond threshold score < 0.98."""
    return compute_reward(predicted, corrected)["score"] < 0.98
