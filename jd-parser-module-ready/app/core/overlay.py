"""Pure-Python correction overlay algorithm ported directly from TypeScript src/app/api/analyze/route.ts lines 73-94."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from app.schemas.requirement import RequirementData


def apply_correction_overlay(
    fresh_llm_result: RequirementData | Dict[str, Any],
    prior_correction: RequirementData | Dict[str, Any],
) -> Dict[str, Any]:
    """Overlay recruiter human corrections on top of fresh LLM extraction results.

    Ports exact loop logic from src/app/api/analyze/route.ts lines 73-94.
    Preserves exact TS branch order and quirks:
    - Iterates over correction keys in order.
    - Branch 1: Only non-empty arrays overwrite (corrVal.length > 0). Empty arrays in correction never overwrite.
    - Branch 2: Non-array, non-null, non-undefined, non-empty, non-'Not specified' values overwrite.
    - Branch 3: If LLM value is 'Not specified', '', or None, assigns corrVal (even if corrVal is empty/missing).
      An empty LLM array [] is NOT counted as empty in Branch 3.
    """
    llm_dict = (
        fresh_llm_result.model_dump(by_alias=True)
        if hasattr(fresh_llm_result, "model_dump")
        else dict(fresh_llm_result)
    )
    corr_dict = (
        prior_correction.model_dump(by_alias=True)
        if hasattr(prior_correction, "model_dump")
        else dict(prior_correction)
    )

    overlaid: Dict[str, Any] = {**llm_dict}

    for key in corr_dict.keys():
        corr_val = corr_dict[key]
        llm_val = llm_dict.get(key)

        # Branch 1
        if isinstance(corr_val, list):
            if len(corr_val) > 0:
                overlaid[key] = corr_val
        # Branch 2
        elif corr_val is not None and corr_val != "Not specified" and corr_val != "":
            overlaid[key] = corr_val
        # Branch 3
        elif llm_val == "Not specified" or llm_val == "" or llm_val is None:
            overlaid[key] = corr_val

    return overlaid
