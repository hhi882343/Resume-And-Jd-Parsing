import time
from typing import Dict, List, Optional, Any
from src.types import ParsedCandidateResume


class CandidateStoreAdapter:
    async def save_candidate(self, candidate: Dict[str, Any]) -> Dict[str, str]:
        raise NotImplementedError

    async def get_candidate_by_id(self, id: str) -> Optional[ParsedCandidateResume]:
        raise NotImplementedError

    async def list_candidates(self, options: Optional[Dict[str, int]] = None) -> List[ParsedCandidateResume]:
        raise NotImplementedError

    async def delete_candidate(self, id: str) -> bool:
        raise NotImplementedError


class InMemoryCandidateStore(CandidateStoreAdapter):
    def __init__(self):
        self._records: Dict[str, ParsedCandidateResume] = {}
        self._counter: int = 1

    async def save_candidate(self, candidate: Dict[str, Any]) -> Dict[str, str]:
        cand_id = f"cand_{self._counter}_{int(time.time() * 1000)}"
        self._counter += 1
        self._records[cand_id] = dict(candidate)  # type: ignore
        return {"id": cand_id}

    async def get_candidate_by_id(self, cand_id: str) -> Optional[ParsedCandidateResume]:
        return self._records.get(cand_id)

    async def list_candidates(self, options: Optional[Dict[str, int]] = None) -> List[ParsedCandidateResume]:
        opts = options or {}
        all_recs = list(self._records.values())
        offset = opts.get("offset", 0)
        limit = opts.get("limit", len(all_recs))
        return all_recs[offset:offset + limit]

    async def delete_candidate(self, cand_id: str) -> bool:
        if cand_id in self._records:
            del self._records[cand_id]
            return True
        return False

    # CamelCase aliases for TS parity
    saveCandidate = save_candidate
    getCandidateById = get_candidate_by_id
    listCandidates = list_candidates
    deleteCandidate = delete_candidate

