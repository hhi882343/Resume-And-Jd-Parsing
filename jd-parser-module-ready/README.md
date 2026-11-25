# JD Parser Engine – Universal ATS Extraction Module

A production-grade, standalone Python engine for parsing unstructured Job Descriptions (JDs) and pasted email text into 28 standardized ATS fields, technical skills matrices, salary/budget structures, and universal email headers.

---

## 🌟 Key Features

- **Universal Email Header Extraction**: Extracts `From`, `To`, `CC`, `Subject`, and `Date` from copied emails. Supports standard RFC headers (Gmail, Apple Mail) and **unlabelled Outlook format** (multiline headers without explicit `From:`/`To:` labels), properly resolving semicolon-separated recipient groups without field swapping.
- **Multi-Role Chunker**: Automatically detects and splits composite emails containing multiple distinct job positions (e.g., "Position 1: Frontend", "Position 2: DevOps") into separate, indexed requirement records with metadata inheritance.
- **Resilient AI Provider Cascade**:
  1. **Primary**: Google Gemini (`gemini-2.5-flash-lite`, fallback chain: `gemini-2.0-flash`, `gemini-flash-latest`, `gemini-3.1-flash-lite`, `gemini-2.5-pro`).
  2. **Fallback 1**: SambaNova Systems (`Meta-Llama-3.3-70B-Instruct`).
  3. **Fallback 2**: Groq Cloud (`llama-3.3-70b-versatile`).
  4. **Fallback 3**: OpenRouter (`meta-llama/llama-3.3-70b-instruct:free`).
  - Automatic exponential backoff, rate limit (`429`) detection, and transparent provider failover.
- **Canonical Skill & Domain Normalization**: Cleans and normalizes technical skills (e.g., `NodeJS` $\rightarrow$ `Node.js`, `AWS / Amazon Web Services` $\rightarrow$ `AWS`), extracts recruiter-specified proficiency ratings (1-5), infers standardized job titles, and standardizes budgets while preserving exact compensation expressions.
- **Zero-Dependency Lightweight Core**: Uses direct asynchronous HTTP calls via `httpx` for LLM provider communication. Does **not** require heavy external SDKs (`google-genai`, `torch`, `transformers`). Can run completely stateless without a database.

---

## 🚀 Quickstart (3 Minutes)

### 1. Installation

Create a virtual environment and install the lean production dependencies:

```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the template configuration and add at least one AI API key (Google Gemini recommended):

```bash
cp .env.example .env
```

Open `.env` and set your key:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
```

*(Optional fallbacks: Add `SAMBANOVA_API_KEY` or `GROQ_API_KEY` for 100% high-availability failover).*

---

## 💻 Usage Methods

### Option A: Direct Python Library (Async / Sync)

```python
from jd_parser import parse_jd, parse_jd_sync, parse_email_headers

raw_email_text = """
TPC - Requirement - PLM - Technical Publication - Bangalore
Kallol Chakraborty<Kallol.Chakraborty@Ltts.com>
Arundhati Shivashankarappa Rudagi <Arundhati.Rudagi_ext@Ltts.com>;Pranati Paul <Pranati.Paul_ext@Ltts.com>
Ashwini Kudi C E <Ashwini.Kudi@Ltts.com>
Dear Partner,

We are looking for a Technical Publication Engineer with 4-5 years of experience.
Location: Bangalore
Budget: 70000 Monthly
Notice Period: Immediate
"""

# 1. Direct Email Header Extraction (Runs instantly, zero LLM calls)
headers = parse_email_headers(raw_email_text)
print(headers["from"])  # [{'name': 'Kallol Chakraborty', 'email': 'kallol.chakraborty@ltts.com'}]
print(headers["to"])    # [{'name': 'Arundhati...', 'email': '...'}, {'name': 'Pranati Paul', 'email': '...'}]
print(headers["cc"])    # [{'name': 'Ashwini Kudi C E', 'email': 'ashwini.kudi@ltts.com'}]

# 2. Synchronous Full ATS Extraction (for Django, Flask, Celery, scripts)
requirements = parse_jd_sync(raw_email_text)
for req in requirements:
    print(f"Role: {req.job_title} | Experience: {req.overall_experience} | Budget: {req.monthly_budget}")

# 3. Asynchronous Full ATS Extraction (for FastAPI, asyncio backends)
# requirements = await parse_jd(raw_email_text)
```

### Option B: Command Line Interface (CLI)

Parse a text or email file directly from terminal:

```bash
# Full ATS requirement extraction to JSON
python jd_parser.py samples/sample_jd_single.txt

# Email headers only (instant extraction)
python jd_parser.py samples/sample_email_unlabelled_outlook.txt --headers-only
```

### Option C: REST API Service (FastAPI)

Launch the high-performance ASGI microservice:

```bash
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

#### Endpoints:

- **`POST /api/analyze`**: Full ATS extraction
  ```bash
  curl -X POST http://localhost:8000/api/analyze \
    -H "Content-Type: application/json" \
    -d '{"rawJdText": "Senior Python Backend Engineer in Bangalore..."}'
  ```
- **`POST /api/email/headers`**: Instant header extraction
  ```bash
  curl -X POST http://localhost:8000/api/email/headers \
    -H "Content-Type: application/json" \
    -d '{"emailText": "From: recruiter@corp.com\nTo: hr@agency.com..."}'
  ```
- **Interactive Documentation**: Visit `http://localhost:8000/docs` (Swagger UI).

---

## 📁 Package Structure

```text
jd-parser-module-ready/
├── README.md                 # Main overview and quickstart guide
├── ARCHITECTURE.md           # Deep dive into parsing pipeline & cascade
├── INTEGRATION_GUIDE.md      # Integration recipes for Django, Flask, FastAPI & Docker
├── CONFIGURATION.md          # Complete environment variable and provider reference
├── FIELD_MAPPING.md          # Detailed 28-field ATS schema mapping
├── DEPENDENCY_AUDIT.md       # Dependency comparison and audit report
├── jd_parser.py              # Top-level Python entry point & CLI
├── pyproject.toml            # Standalone package definition
├── requirements.txt          # Lean production dependencies
├── .env.example              # Configuration template with zero secrets
│
├── app/                      # Production Extraction Core
│   ├── api/                  # FastAPI routers and JSON response formatting
│   ├── core/                 # Chunker, email extractor, normalizer, reward
│   ├── schemas/              # Pydantic v2 domain schemas (28 ATS fields)
│   ├── services/             # LLM cascade client, prompt templates, orchestration
│   ├── config.py             # Pydantic Settings loader
│   └── main.py               # FastAPI application factory
│
├── samples/                  # Sanitized test samples
│   ├── sample_jd_single.txt
│   ├── sample_jd_multiple_roles.txt
│   ├── sample_email_labelled.txt
│   ├── sample_email_unlabelled_outlook.txt
│   ├── sample_output_single.json
│   └── sample_output_email_headers.json
│
└── tests/                    # Offline automated verification suite
    ├── fixtures/golden/      # Golden JSON fixtures for deterministic testing
    ├── test_parser_module.py # Top-level SDK & CLI tests
    ├── test_core_*.py        # Engine unit tests (email, chunker, normalizer)
    └── test_schemas.py       # Pydantic ATS contract validation tests
```

---

## 🧪 Automated Testing

The module comes with an offline test suite of **456 unit tests** covering email extraction, multi-role partitioning, skill normalization, and schema validation. Tests run deterministically against golden fixtures without requiring network access or live API keys:

```bash
pytest
```

Expected result:
```text
======================= 456 passed in 2.4s =======================
```

---

## 📄 License & Distribution

Internal Handover Module – MIT License.
Designed for drop-in integration into recruitment portals, ATS systems, and backend ETL pipelines.

