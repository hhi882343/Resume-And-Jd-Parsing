# JD Parser Module – Architecture & Pipeline Specification

## 1. System Overview

The **JD Parser Engine** is designed as a modular, resilient information extraction pipeline capable of converting highly unstructured recruitment text and raw email pastes into strictly validated ATS (Applicant Tracking System) records.

```text
                                  [ Raw Input Text / Copied Email ]
                                                 │
                                                 ▼
                             ┌───────────────────────────────────────┐
                             │ Stage 1: Ingestion & Normalization   │
                             │ - Unicode newline normalization       │
                             │ - Quote & whitespace sanitization     │
                             └───────────────────┬───────────────────┘
                                                 │
                                                 ▼
                             ┌───────────────────────────────────────┐
                             │ Stage 2: Universal Email Header Extr. │
                             │ - RFC 2822 labeled parser (Gmail)     │
                             │ - Outlook unlabelled multi-line parser│
                             │ - Recipient grouping (From, To, CC)   │
                             │ - Header boundary detection           │
                             └───────────────────┬───────────────────┘
                                                 │
                                                 ▼
                             ┌───────────────────────────────────────┐
                             │ Stage 3: Multi-Role Chunker           │
                             │ - Position focus marker detection     │
                             │ - Requirement boundary partitioning   │
                             │ - Common metadata extraction          │
                             └───────────────────┬───────────────────┘
                                                 │
                        ┌────────────────────────┴────────────────────────┐
                        │ Concurrent Extraction per Role (asyncio.gather)  │
                        ▼                                                 ▼
        ┌───────────────────────────────┐                 ┌───────────────────────────────┐
        │ Stage 4: LLM Cascade Client   │                 │ Stage 4: LLM Cascade Client   │
        │ - Primary: Google Gemini      │                 │ - Primary: Google Gemini      │
        │ - Fallback 1: SambaNova Llama │                 │ - Fallback 1: SambaNova Llama │
        │ - Fallback 2: Groq Llama      │                 │ - Fallback 2: Groq Llama      │
        │ - Fallback 3: OpenRouter      │                 │ - Fallback 3: OpenRouter      │
        └───────────────┬───────────────┘                 └───────────────┬───────────────┘
                        │                                                 │
                        ▼                                                 ▼
        ┌───────────────────────────────┐                 ┌───────────────────────────────┐
        │ Stage 5: Normalization & RegEx│                 │ Stage 5: Normalization & RegEx│
        │ - Canonical skill mappings    │                 │ - Canonical skill mappings    │
        │ - Experience/Notice parsing   │                 │ - Experience/Notice parsing   │
        │ - Budget expression preserving│                 │ - Budget expression preserving│
        └───────────────┬───────────────┘                 └───────────────┬───────────────┘
                        │                                                 │
                        └────────────────────────┬────────────────────────┘
                                                 │
                                                 ▼
                             ┌───────────────────────────────────────┐
                             │ Stage 6: Schema Assembly & Validation │
                             │ - 1-based indexing (roleIndex)        │
                             │ - Metadata inheritance merge          │
                             │ - Pydantic v2 CamelModel validation   │
                             └───────────────────┬───────────────────┘
                                                 │
                                                 ▼
                              [ Standardized ATS Output List (JSON) ]
```

---

## 2. Detailed Pipeline Stages

### Stage 1: Text Ingestion & Sanitization
- Normalizes carriage returns (`\r\n` $\rightarrow$ `\n`).
- Normalizes fancy Unicode quotation marks, bullet points (`•`, `*`, `-`), and zero-width spaces.
- Strips trailing email client garbage, confidentiality disclaimers, and tracking footers.

### Stage 2: Universal Email Header Extraction Engine (`app/core/email_extractor.py`)
Recruitment demands often arrive via copied email text from various email clients. The extractor handles:
1. **Labeled RFC Headers**: Standard headers with explicit prefixes (`From:`, `To:`, `Cc:`, `Subject:`, `Date:`).
2. **Unlabelled Outlook Copied Emails**: When users highlight text in Outlook and copy-paste, labels are stripped:
   ```text
   Subject Line
   Sender Name<sender@company.com>
   Recipient 1 <r1@vendor.com>; Recipient 2 <r2@vendor.com>
   CC Recipient <cc@company.com>
   Dear Partner,
   ```
3. **Structured Semicolon/Comma Parsing**:
   - Parses multi-recipient blocks separated by `;` or `,`.
   - Handles missing spaces in angle brackets: `Name<
   email@domain.com>`.
   - Extracts both display name and canonical lowercase email.
4. **Boundary Detection**: Identifies salutations (`Dear`, `Hi Team`) or JD section markers (`Position:`, `Responsibilities:`) to prevent body email addresses (e.g., HR contact inside signature) from polluting header fields.
5. **Independent Missing Field Handling**: If `CC` is absent, it remains empty (`[]` / `"Not specified"`); it is never populated with the `From` address.

### Stage 3: Multi-Role Chunker (`app/core/chunker.py`)
Recruiters frequently send multiple open positions in a single email. The chunker:
- Scans for numbered or tagged role markers (e.g., `Position 1: React Lead`, `Position 2: Cloud Architect`, `Role A:`, `Requirement #2`).
- When multiple roles are identified, extracts common header/footer metadata (client name, POCs, email headers) and partitions the body into separate requirement chunks.
- If no explicit markers exist, applies LLM-assisted partitioning to detect multiple role boundaries.

### Stage 4: Concurrent LLM Cascade (`app/services/llm_client.py`)
Each requirement chunk is extracted concurrently using `asyncio.gather` while maintaining exact 1-based role index order.
The cascade architecture guarantees high availability:
- **Primary: Google Gemini** (`gemini-2.5-flash-lite`, with internal fallbacks: `gemini-2.0-flash`, `gemini-flash-latest`, `gemini-3.1-flash-lite`, `gemini-2.5-pro`).
- **Fallback 1: SambaNova Systems** (`Meta-Llama-3.3-70B-Instruct`).
- **Fallback 2: Groq Cloud** (`llama-3.3-70b-versatile`).
- **Fallback 3: OpenRouter** (`meta-llama/llama-3.3-70b-instruct:free`).

#### Failover Conditions:
- HTTP status `429` (Rate Limit Exceeded)
- HTTP status `503` (Service Unavailable / Overloaded)
- Quota exhaustion or timeout
- Transparent automatic switchover with zero data loss

### Stage 5: Normalization & Heuristic Augmentation (`app/core/normalize.py`)
Raw LLM outputs are post-processed through deterministic rule engines:
- **Canonical Skills**: Maps variant skill spellings to industry-standard nomenclature:
  - `NodeJS` / `Node js` $\rightarrow$ `Node.js`
  - `ReactJS` / `React.js` $\rightarrow$ `React`
  - `Postgres` $\rightarrow$ `PostgreSQL`
  - `AWS / Amazon Web Services` $\rightarrow$ `AWS`
- **Budget Preservation**: Standardizes numerical amounts while preserving exact contractual terms (e.g., `"20-25 LPA"`, `"70,000/month"`, `"$85/hr corp-to-corp"`).
- **Date Standardization**: Standardizes date stamps against application timezone using frozen clock abstraction.

### Stage 6: Schema Assembly (`app/schemas/requirement.py`)
Builds validated Pydantic v2 `AnalyzedRequirement` instances:
- Automatically injects `requirementId` (formatted as `REQ-YYYY-MM-DD-XXX`).
- Sets `roleIndex` and `totalRoles`.
- Records `extractionSource` (`"gemini"`, `"sambanova"`, `"groq"`, etc.).
- Inherits common metadata from Stage 2/3 for multi-role demands.

---

## 3. Stateless vs. State-Persistent Modes

The engine supports two operational modes:

| Mode | Invocation | Database Required? | Use Case |
| :--- | :--- | :--- | :--- |
| **Stateless (Default)** | `parse_jd(text)` / `parse_jd_sync(text)` | **No** (Zero DB interaction) | Microservices, AWS Lambda, Celery workers, ETL pipelines, CLI scripts. |
| **State-Persistent** | `orchestrate_analysis(text, session=db_session)` | **Optional** (SQLite / MySQL) | Full application with human-in-the-loop correction storage and RL/DPO training data collection. |

When `session is None`, all database reads, writes, and foreign key validations are completely bypassed, allowing the module to run as a pure function.

