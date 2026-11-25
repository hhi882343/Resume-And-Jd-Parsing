# JD Parser Module – Dependency Audit & Cleanup Report

This audit documents the rationale for all retained and removed packages, files, and modules during the extraction of the standalone handover package.

---

## 1. Package Dependency Comparison

| Package Category | Original Project (`pyproject.toml`) | Standalone Handover Module | Audit Rationale & Justification |
| :--- | :--- | :--- | :--- |
| **API & Server** | `fastapi`, `uvicorn[standard]` | `fastapi`, `uvicorn[standard]` | **Retained**: Essential for REST microservice endpoints (`/api/analyze`, `/api/email/headers`). |
| **Data & Validation** | `pydantic>=2.9`, `pydantic-settings` | `pydantic>=2.6`, `pydantic-settings` | **Retained**: Powers 28-field ATS schemas, CamelModel serialization, and environment configuration. |
| **HTTP & AI Clients** | `httpx>=0.27`, `requests` | `httpx>=0.27` | **Retained & Streamlined**: Direct async HTTP calls handle all AI providers (Gemini, SambaNova, Groq, OpenRouter). `requests` removed in favor of `httpx`. |
| **Heavy AI SDKs** | `google-genai`, `google-generativeai` | *None (Removed)* | **Removed**: Direct REST calls via `httpx` eliminate ~150MB of transitive dependencies while achieving identical response times and eliminating version deprecation churn. |
| **Frontend & UI** | `streamlit`, `pandas`, `altair` | *None (Removed)* | **Removed**: The Streamlit user interface is irrelevant for a standalone backend parser and would add unnecessary UI server overhead. |
| **ML & Training** | `torch`, `transformers`, `trl`, `peft`, `datasets`, `accelerate`, `bitsandbytes` | *None (Removed)* | **Removed**: Fine-tuning scripts for offline DPO model alignment are separated from production inference/extraction. Eliminates >3 GB of heavy ML dependencies. |
| **Database Migrations**| `alembic`, `pymysql`, `cryptography` | *None (Removed)* | **Removed**: Standalone parser runs 100% stateless in memory. Production DB migrations and MySQL drivers belong in the host application's infrastructure. |
| **Storage & ORM** | `sqlalchemy>=2.0`, `aiosqlite` | `sqlalchemy>=2.0`, `aiosqlite` | **Retained (Lean)**: Zero-config embedded SQLite support retained if human correction storage is used. |
| **Testing** | `pytest>=8.0`, `pytest-asyncio` | `pytest>=8.0`, `pytest-asyncio` | **Retained**: Ensures offline deterministic verification across 456 unit tests. |

---

## 2. Directory & File Inventory

### Retained Production Files (Included in Handover Package):
- `app/api/`: FastAPI route handlers and exact JSON response formatters.
- `app/core/`:
  - `chunker.py`: Multi-role detection, header stripping, chunking.
  - `clock.py`: System clock / time abstraction.
  - `email_extractor.py`: Universal Email Header Extraction (labeled + Outlook unlabelled formats).
  - `normalize.py`: Skill canonicalization, salary/compensation standardization, experience normalization.
  - `overlay.py`: Correction overlay engine.
  - `reward.py` & `reward_scorer.py`: Scoring utilities.
- `app/schemas/`: ATS contract schemas (`AnalyzedRequirement`, `RequirementData`, `EmailContactSchema`).
- `app/services/`: Cascade LLM client, prompt templates, extraction orchestrator.
- `jd_parser.py`: Direct Python library interface (`parse_jd`, `parse_jd_sync`, `parse_email_headers`, CLI).
- `samples/`: Sanitized input and output examples.
- `tests/`: 456 automated unit tests with offline golden boundary fixtures.

### Removed Non-Essential Files (Excluded from Handover Package):
- `ui/`: Removed Streamlit UI files (`jd_ui.py`, `markup.py`, `format.py`, `runtime.py`, `components/`).
- `training/`: Removed local model fine-tuning script (`dpo_train.py`).
- `archive/`: Removed legacy prototypes and scripts (`legacy-python/backend_engine.py`, `streamlit_app.py`).
- `scripts/`: Removed one-off porting scripts (`audit_coalesce.py`, `find_dates.py`, `import_legacy_sqlite.py`, `probe_nextjs.*`).
- `data/`: Removed local binary database and training files (`feedback.db`, `feedback.db.bak`, `dpo-preference-pairs.jsonl`).
- `docs/`: Removed internal porting notes (`migration-plan.md`, `port-notes.md`, `ui-parity-checklist.md`, `ui-plan.md`).
- `.streamlit/`, `.pytest_cache/`, `.ruff_cache/`, `jd_analyser.egg-info/`: Removed cache and build artifacts.

---

## 3. Security & Safety Evaluation

1. **Zero Secret Leakage**:
   - `.env.example` contains variable names and placeholder strings only.
   - No real API keys, tokens, passwords, or production URLs are present anywhere in the handover package.
2. **Deterministic Offline Testing**:
   - Tests run strictly against recorded golden fixtures in `tests/fixtures/golden/`.
   - Tests do not attempt outbound network connections or depend on external service uptime.
3. **Safe Parsing & Execution**:
   - No `eval()`, `exec()`, or unsafe deserialization (`pickle`) is used.
   - Pydantic v2 enforces strict type validation and limits memory usage during parsing.
   - Regex patterns are bounded to prevent catastrophic backtracking (ReDoS).

