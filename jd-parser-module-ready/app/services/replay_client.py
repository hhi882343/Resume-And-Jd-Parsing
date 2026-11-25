"""Replay LLM client for offline deterministic testing against golden test fixtures.

Loads recorded outputs from tests/fixtures/golden/llm_boundary.json.
Guarantees that tests never make live network calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.llm_client import BaseLLMClient


class ReplayLLMClient(BaseLLMClient):
    """Offline replay LLM client keyed against tests/fixtures/golden/llm_boundary.json."""

    def __init__(
        self,
        fixtures_path: Optional[str | Path] = None,
        default_source: str = "synthetic-baseline",
    ) -> None:
        self._fixtures_path = Path(fixtures_path or "tests/fixtures/golden/llm_boundary.json")
        self._default_source = default_source
        self._records: List[Dict[str, Any]] = []
        self._by_sample_id: Dict[str, Dict[str, Any]] = {}
        self._by_raw_text: Dict[str, Dict[str, Any]] = {}
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._last_source: str = default_source
        self._load_fixtures()

    def _load_fixtures(self) -> None:
        if not self._fixtures_path.exists():
            return

        with open(self._fixtures_path, "r", encoding="utf-8") as f:
            self._records = json.load(f)

        for rec in self._records:
            rec_id = rec.get("id")
            if rec_id:
                self._by_id[rec_id] = rec

            inp = rec.get("input", {})
            sample_id = inp.get("sample_id")
            if sample_id:
                self._by_sample_id[sample_id] = rec

            raw_text = inp.get("raw_text")
            if raw_text:
                self._by_raw_text[raw_text.strip()] = rec

    @property
    def provider_name(self) -> str:
        return self._last_source

    def find_record(
        self,
        prompt: str,
        *,
        raw_text: Optional[str] = None,
        sample_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find matching golden fixture record by sample_id, raw_text, or prompt content."""
        if sample_id and sample_id in self._by_sample_id:
            return self._by_sample_id[sample_id]

        if raw_text and raw_text.strip() in self._by_raw_text:
            return self._by_raw_text[raw_text.strip()]

        # Try matching by prompt substring
        for recorded_text, rec in self._by_raw_text.items():
            if recorded_text in prompt or prompt.strip() == recorded_text:
                return rec

        return None

    async def extract(
        self,
        prompt: str,
        *,
        raw_text: Optional[str] = None,
        sample_id: Optional[str] = None,
        json_mode: bool = True,
        retries_per_model: int = 3,
    ) -> str:
        """Serve recorded JSON extraction for matching input record."""
        rec = self.find_record(prompt, raw_text=raw_text, sample_id=sample_id)
        if not rec:
            raise KeyError(
                f"ReplayLLMClient: no recorded golden boundary record found for prompt/sample_id={sample_id!r}"
            )

        expected = rec.get("expected_output", {})
        self._last_source = expected.get("source", self._default_source)
        extracted = expected.get("extracted_data", {})

        # In offline synthetic baseline mode (generate_fixtures.ts),
        # the simulated raw LLM response provided {jobTitle, jobDescription}.
        # Domain normalization and regex augmentation are then applied during finalize_extraction.
        if self._last_source == "synthetic-baseline":
            raw_response = {
                "jobTitle": extracted.get("jobTitle"),
                "jobDescription": extracted.get("jobDescription"),
            }
            return json.dumps(raw_response)

        return json.dumps(extracted)
