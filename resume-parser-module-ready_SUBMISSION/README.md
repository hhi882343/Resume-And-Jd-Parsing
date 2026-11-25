# Resume Parser Module (Production Ready)

A self-contained, enterprise-grade resume parsing engine for Node.js and TypeScript. It features a dual-engine architecture:
1. **Primary AI Parsing Engine**: Powered by Google Generative AI (Gemini 3.8 Flash, with automatic multi-model fallback across Gemini 2.5 Flash, 2.0 Flash, and 1.5 Flash).
2. **Local Deterministic Fallback Parser**: A zero-external-dependency heuristic engine with regex and dictionary rules that activates automatically when Gemini API quota is exhausted, offline, or when no API key is configured.
3. **Evidence-Lock Verification**: Enforces post-extraction validation to ensure that all extracted skills, roles, experience numbers, and locations have explicit verbatim backing in the source resume document, preventing hallucinations.
4. **AI Context Chat**: Includes candidate assessment Q&A endpoint and function to evaluate candidates against job descriptions or query resumes interactively.
5. **Storage Adapters**: Includes clean persistence abstraction 
(`CandidateStoreAdapter`) with a default `InMemoryCandidateStore` and instructions for plugging in PostgreSQL, Prisma, MongoDB, or SQLite.

---

## Why the Source Code Package Size is ~250 KB (and Why That is Normal)

In the original full-stack repository, the folder `metaforge-resume-parser` measured ~1.56 MB. However:
- **1.137 MB** was a binary SQLite write-ahead-log (`metaforge.db-wal`).
- **67 KB** was `package-lock.json`.
- **36 KB** were SQLite database headers (`metaforge.db`, `metaforge.db-shm`).

None of those binary database files were resume parsing code. Pure, clean TypeScript source code without `node_modules` or database binaries is approximately **250 KB** (spanning ~5,000 lines of code across all parsers, regex engines, schemas, prompts, and utilities). The complete Python package is ~800 KB.

---

## Architecture Overview

```
                                ┌────────────────────────┐
                                │   Uploaded Resume      │
                                │ (PDF, DOCX, DOC, TXT)  │
                                └───────────┬────────────┘
                                            │
                                            ▼
                       ┌─────────────────────────────────────────┐
                       │      extractResumeText / extract.ts     │
                       │   (pdf-parse, mammoth, word-extractor)  │
                       └────────────────────┬────────────────────┘
                                            │
                        ┌───────────────────┴───────────────────┐
                        │ Is GEMINI_API_KEY set & quota valid?  │
                        └─────────┬───────────────────┬─────────┘
                                  │ YES               │ NO (or Quota 429)
                                  ▼                   ▼
                     ┌───────────────────────┐   ┌───────────────────────┐
                     │   Gemini AI Parser    │   │  Local Deterministic  │
                     │  (gemini-3.8-flash)   │   │     Regex Parser      │
                     └───────────┬───────────┘   └───────────┬───────────┘
                                 │                           │
                                 └─────────────┬─────────────┘
                                               │
                                               ▼
                              ┌──────────────────────────────────┐
                              │     applyEvidenceLock Engine     │
                              │  - Strict 10-skill cap           │
                              │  - Dedicated skills section lock │
                              │  - Professional role validation  │
                              │  - Explicit experience cleaner   │
                              │  - Location extraction & lock    │
                              └────────────────┬─────────────────┘
                                               │
                                               ▼
                                 ┌────────────────────────────┐
                                 │   Normalized Output JSON   │
                                 │  (ParsedCandidateResume)   │
                                 └────────────────────────────┘
```

---

## Directory Structure

```
resume-parser-module-ready/
├── .env.example                 # Sanitized configuration template
├── README.md                    # Comprehensive documentation & API reference
├── PORT_NOTES.md                # Porting decisions, architectural logs, and parity evidence
├── AUDIT.md                     # Security, dependency, and vulnerability audit
├── app.py                       # Streamlit interactive UI application & server launcher
├── requirements.txt             # Pinned Python dependencies
├── pytest.ini                   # Pytest test suite configuration
├── sample_resume.txt            # Deterministic test fixture resume
├── assets/
│   └── tessdata/eng.traineddata # Verified OCR trained data model
├── src/
│   ├── __init__.py              # Package public exports
│   ├── server.py                # Standalone FastAPI/ASGI service
│   ├── types.py                 # Pydantic models & type definitions
│   ├── metaforgeParser.py       # Orchestrator & Evidence-Lock pipeline
│   ├── parseCoreResumeFields.py # Deterministic regex & heuristic local parser
│   ├── skillsExtractionEngine.py# Modular skills extraction & 10-skill cap engine
│   ├── coreTechKeywords.py      # Dictionary of technical skills & phrases
│   ├── extractResumeText.py     # Multi-format document text extractor & OCR
│   ├── candidateNameValidation.py# Candidate name sanitation and header filter
│   ├── resumeFieldSanitize.py   # Education normalizer and string cleaners
│   ├── jsRegex.py               # JavaScript V8 RegExp engine emulator
│   ├── ai/
│   │   ├── config.py            # AI environment configuration & model fallback lists
│   │   ├── gemini.py            # Native HTTP client for Google Generative AI REST API
│   │   ├── prompt.py            # Strict extraction system prompts
│   │   ├── schema.py            # JSON cleaning, markdown fence stripper & validator
│   │   ├── experience.py        # Work experience duration calculator
│   │   ├── normalize.py         # Phone and contact normalizer
│   │   ├── pdfText.py           # PDF page layout text extractor
│   │   └── extract.py           # Base64 and text payload preparer
│   └── routes/
│       └── resumeParserRouter.py# FastAPI router for /parse, /parse/bulk, /health
├── tests/                       # Complete pytest regression & parity test suite
└── tools/                       # Subprocess binary extraction bridge helpers
```

---

## System Requirements & Dependencies

- **Node.js**: `>= 18.0.0` (tested on Node 18, 20, 22, and 24)
- **TypeScript**: `>= 5.0.0`
- **Native Fetch**: Uses standard global `fetch` (built into Node 18+). No external `@google/generative-ai` SDK is required, keeping bundle size minimal and avoiding dependency bloat.

### Runtime Dependencies
| Package | Version | Purpose |
| :--- | :--- | :--- |
| `express` | `^4.21.2` | HTTP router adapter and standalone service |
| `cors` | `^2.8.5` | Cross-origin resource sharing middleware |
| `multer` | `^1.4.5-lts.1` | In-memory multipart file upload handling (no disk writes) |
| `pdf-parse` | `^1.1.1` | Fast PDF text and metadata extraction |
| `mammoth` | `^1.8.0` | Microsoft Word (`.docx`) text extraction |
| `word-extractor`| `^1.0.4` | Legacy Microsoft Word (`.doc`) binary extraction |
| `pdfjs-dist` | `^5.7.284` | PDF page rendering for OCR fallback |
| `tesseract.js` | `^7.0.0` | Optional OCR engine for scanned PDF and image resumes |
| `@napi-rs/canvas` | `^1.0.0` | Canvas backend for PDF OCR rendering |
| `dotenv` | `^16.4.7` | Loads environment variables from `.env` |

---

## Configuration (`.env`)

Copy `.env.example` to `.env` in the root of your application:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `GEMINI_API_KEY` | Optional | `""` | Google Gemini API key. If omitted, the module operates in **100% deterministic local mode** without cloud calls. |
| `GEMINI_MODEL` | Optional | `gemini-3.8-flash` | Primary Gemini model ID (also accepts alias `GEMINI_RESUME_MODEL`). Automatically falls back on rate limits. |
| `GEMINI_FALLBACK_MODELS` | Optional | `gemini-3.5-flash-lite,gemini-3.5-flash` | Comma-separated list of fallback models if primary model hits 429 quota or rate limits. |
| `PORT` | Optional | `3001` | HTTP port when running as a standalone server. |
| `CORS_ORIGIN` | Optional | `*` | Allowed CORS origins for Express API server. |

---

## Quick Start & Integration Guide

### Option 1: Integrate as an In-Process Library (Recommended)

Import `parseResumeBuffer` directly into your existing backend controllers or worker queues:

```typescript
import fs from 'fs';
import { parseResumeBuffer, ParsedCandidateResume } from 'resume-parser-module';

async function handleCandidateUpload() {
  const fileBuffer = fs.readFileSync('path/to/resume.pdf');
  const filename = 'resume.pdf';

  // Automatically uses Gemini AI if key is set, or falls back to local parser
  const result: ParsedCandidateResume = await parseResumeBuffer(fileBuffer, filename);

  console.log('Candidate Name:', result.candidateName);
  console.log('Designation / Role:', result.technologiesRaw);
  console.log('Skills (max 10):', result.skillsRaw);
  console.log('Total Experience:', result.totalExperience);
  console.log('Location:', result.currentLocation);
  console.log('Contact Number:', result.contactNumber);
  console.log('Email:', result.email);
  console.log('Highest Qualification:', result.highestQualification);
  console.log('Parser Used:', result.parser); // 'metaforge' | 'legacy'
}
```

### Option 2: Mount as an Express Route in Your Existing API

Mount the provided `resumeParserRouter` directly into your Express application:

```typescript
import express from 'express';
import { resumeParserRouter } from 'resume-parser-module';

const app = express();
app.use(express.json());

// Mount at your desired base path
app.use('/api/candidates/resume', resumeParserRouter);

app.listen(3000, () => {
  console.log('Application running with resume parsing at /api/candidates/resume/parse');
});
```

### Option 3: Run as a Standalone Microservice

Run the included microservice server independently:

```bash
# Start standalone parser service
uvicorn src.server:app --host 127.0.0.1 --port 3001 --workers 1

# Start Streamlit UI
streamlit run app.py
```

### Running the UI
streamlit run app.py. Features dedicated tabs for **Single Resume** and **Bulk Upload** (max 5 files). Behaviour matches the original service; extraction accuracy improvements are planned as a later version.
Configurable via `RESUME_PARSER_URL` (defaults to `http://127.0.0.1:3001` or `PORT` environment variable). Note that if the UI automatically starts the backend service, it may leave the service running after the browser window closes.

---

## Quick Start

### 1. Prerequisites
- **Python**: `Python 3.13` (or `>= 3.11`)
- **Node.js**: `Node 20+` (or `>= 18.0.0`, required for document text extraction helpers in `tools/`)
- **Tesseract OCR**: Optional via winget (`winget install UB-Mannheim.TesseractOCR`, required only for image OCR parsing via `tesseract` on system PATH)

### 2. Installation & Run
```bash
# 1. Create and activate a Python virtual environment
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate       # Windows PowerShell

# 2. Install Python runtime dependencies
pip install -r requirements.txt

# 3. Install Node.js helper dependencies for tools/
cd tools && npm ci --omit=dev && cd ..

# 4. Create environment configuration (Note: .env must never be committed or shared)
copy .env.example .env          # Windows Command Prompt / PowerShell
# cp .env.example .env          # Linux / macOS

# 5. Start the Python backend service
uvicorn src.server:app --host 127.0.0.1 --port 3001 --workers 1

# 6. Start the Streamlit UI (optional)
streamlit run app.py
```

### 3. Verify Health
In a separate terminal:
```bash
curl http://localhost:3001/health
# Response: {"status":"ok","service":"resume-parser-module","aiParserAvailable":false,"aiSuspendedNotice":null,"mode":"local-deterministic"}
```

---

## HTTP API Reference

### 1. Health & Status
- **Method**: `GET`
- **Path**: `/health` (or `/api/resume/health`)
- **Response**:
```json
{
  "status": "ok",
  "service": "resume-parser-module",
  "aiParserAvailable": true,
  "aiSuspendedNotice": null,
  "mode": "hybrid-ai-with-fallback"
}
```

### 2. Parse Single Resume
- **Method**: `POST`
- **Path**: `/parse` (or `/api/resume/parse`)
- **Content-Type**: `multipart/form-data`
- **Form Field**: `resume` (File)
- **Supported File Types**: `.pdf`, `.docx`, `.doc`, `.txt`, `.png`, `.jpg`, `.jpeg`, `.tiff`
- **Sample Response**:
```json
{
  "success": true,
  "message": "Resume parsed successfully",
  "data": {
    "candidateName": "Ananya Sharma",
    "email": "ananya.sharma@gmail.com",
    "contactNumber": "+919876543210",
    "linkedinUrl": "https://linkedin.com/in/ananyasharma",
    "highestQualification": "B.Tech in Computer Science",
    "skillsRaw": "TypeScript, React, Node.js, PostgreSQL, Docker",
    "technologiesRaw": "Full Stack Developer",
    "technologies": "Full Stack Developer",
    "role": "Full Stack Developer",
    "totalExperience": "4 years",
    "relevantExperience": null,
    "currentEmployer": null,
    "currentLocation": "Bangalore, Karnataka",
    "location": "Bangalore, Karnataka",
    "sourceFile": "candidate_resume.pdf",
    "parser": "metaforge"
  }
}
```

### 3. Bulk Resume Parsing
- **Method**: `POST`
- **Path**: `/parse/bulk` (or `/api/resume/parse/bulk`)
- **Content-Type**: `multipart/form-data`
- **Form Field**: `resumes` (Up to 5 files)

### 4. Interactive AI Candidate Q&A / Chat
- **Method**: `POST`
- **Path**: `/chat` (or `/api/resume/chat`)
- **Content-Type**: `application/json`
- **Body**:
```json
{
  "messages": [
    { "role": "user", "content": "Does this candidate have experience with Kubernetes and CI/CD pipelines?" }
  ],
  "candidateProfile": {
    "candidateName": "Ananya Sharma",
    "skillsRaw": "TypeScript, React, Node.js, PostgreSQL, Docker, Kubernetes",
    "totalExperience": "4 years"
  }
}
```

---

## Output Data Contract (`ParsedCandidateResume`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `candidateName` | `string \| null` | Sanitized person name. Never returns resume headings (e.g. "Curriculum Vitae"). |
| `email` | `string \| null` | Validated candidate email address. |
| `contactNumber` | `string \| null` | Cleaned phone number formatted with country code (e.g. `+919876543210`). |
| `linkedinUrl` | `string \| null` | Full HTTPS URL to the candidate's LinkedIn profile. |
| `highestQualification`| `string \| null`| Standardized academic degree (e.g. `B.Tech`, `B.Com`, `MBA`). Non-academic courses and certifications are excluded. |
| `skillsRaw` | `string \| null` | Comma-separated list of **maximum 10** individual skills strictly verified against the resume's skills section. |
| `technologiesRaw` | `string \| null` | Professional designation or primary role title (e.g. `Full Stack Developer`). |
| `role` | `string \| null` | Alias of `technologiesRaw` matching candidate role. |
| `totalExperience` | `string` | Verbatim stated experience (e.g. `12 years`, `7+ years`, `4.5 years`). Qualifiers like "nearly" or "over" are stripped. |
| `relevantExperience` | `null` | Reserved for integration adapters; returns `null`. |
| `currentEmployer` | `string \| null` | Most recent company name if identified. |
| `currentLocation` | `string \| null` | Candidate's current residential location/city/state if stated. |
| `location` | `string \| null` | Alias of `currentLocation`. |
| `sourceFile` | `string` | The original uploaded filename. |
| `parser` | `'metaforge' \| 'legacy'` | Indicates whether Gemini AI (`metaforge`) or the local fallback parser (`legacy`) processed the document. |

---

## Strict Extraction Rules & Evidence Lock Guarantees

1. **Skills Extraction (Maximum 10 Skills)**:
   - Skills are extracted **only** from dedicated skills headings (`Skills`, `Technical Skills`, `Key Skills`, `Core Competencies`, `Tools & Technologies`, etc.).
   - Responsibilities, job duties, project narratives, certificates, and soft skill phrases are strictly excluded.
   - Compound phrases (e.g., `AutoCAD, SolidWorks, CATIA`) are expanded into distinct individual items.
   - Output is strictly capped at **10 unique, deduplicated skills**.
2. **Designation & Role Priority**:
   - The `technologies` / `role` field extracts the professional title using a 4-tier priority hierarchy:
     1. Dedicated Professional Summary / Profile statement.
     2. Resume headline immediately adjacent to the candidate's name.
     3. Explicit employment history designation (e.g. `Designation: Senior Data Engineer`).
     4. `null` if no explicit designation exists (skills are never substituted as the role).
3. **Experience Calculation**:
   - Explicitly stated total experience (e.g. `Over 7 years` -> `7 years`, `7+ years` -> `7+ years`) takes absolute priority over date range arithmetic.
   - If no explicit total duration is declared, returns `""` rather than guessing or fabricating.
4. **Location Extraction**:
   - Labeled location entries (`Current Location: ...`, `Location: ...`, `Based in: ...`) and City, State patterns are extracted and validated.
5. **Evidence Lock**:
   - Even when Gemini AI parses a document, `applyEvidenceLock` validates the AI output against the original extracted text. Any hallucinated skill, location, or designation without text evidence is discarded.

---

## Testing & Verification

The package includes 8 complete test suites with 153 test cases covering all edge cases, regression guarantees, document formats, and HTTP endpoints:

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch
```

### Test Suite Summary
- `tests/candidateNameValidation.test.ts`: Verifies rejection of section headers mistaken for names.
- `tests/parseCoreResumeFields.name.test.ts`: Header suppression and name precedence tests.
- `tests/resumeFieldSanitize.test.ts`: Degree compaction and job role phrase detection.
- `tests/designationExtraction.test.ts`: 4-tier designation priority and bulk candidate isolation.
- `tests/skillsExtractionEngine.test.ts`: Complex table layouts, two-column formats, compound expansion, and strict 10-skill cap.
- `tests/strictSkillsAndExperience.test.ts`: Comprehensive experience string parser and qualifier cleaners.
- `tests/resumeParserRouter.test.ts`: End-to-end integration tests for Express routes and file uploads.
- `tests/documentFormatExtraction.test.ts`: Multi-format text processing, location preservation, and candidate storage adapter tests.

---

## Clean Architecture & Portability

- **Zero Database Lock-In**: The module has no mandatory database dependencies. An optional `CandidateStoreAdapter` is provided for applications wishing to persist parsed records.
- **Zero Authentication Lock-In**: The parsing engine is completely decoupled from JWT, session, or project-specific auth middleware.
- **Self-Contained AI Client**: Built with native HTTPS `fetch`, requiring no external cloud SDK dependencies.
- **Safe For Integration**: Can be safely dropped into any existing TypeScript, JavaScript, Express, NestJS, Fastify, or serverless project.

---

## Python Port & Runtime Dependencies

The Python port (`FastAPI` / `Uvicorn`) provides 100% Gate 2 parity with the original TypeScript service.

### Environment & Binary Dependencies
- **`NODE_BIN`**: Path to the Node.js executable used by child-process binary extractors (`tools/pdf_text.js`, `tools/doc_text.js`, `tools/pdf_parse_text.js`). Defaults to `node` from the system PATH.
- **`TZ`**: Standardized to `UTC`. Note that the original Node development service ran with local host timezone (`Asia/Kolkata` / IST); date boundary formatting in UTC is standard.
- **`GEMINI_API_KEY`**: Optional API key for Gemini AI parser. If empty or absent, the service falls back deterministically to the local regex parser with evidence lock. See `.env.example`.
- **System Binaries**: For native OCR and document text extraction, `node` (Node.js runtime) and `tesseract-ocr` (with `eng.traineddata`) must be available on the system PATH.

---

## Known Limitations

> [!IMPORTANT]
> **Security Notice**: `.env` contains local environment settings and API keys. `.env` must never be committed or shared.

1. **Error Text for Corrupt or Encrypted PDFs**: Error text for corrupt or encrypted PDFs may differ from the original service; HTTP status is the same.
2. **Node.js Runtime Required for Document Helpers**: Node required for PDF/.doc. Extraction of PDF text and legacy `.doc` binary formats utilizes subprocess bridge scripts in `tools/` (`pdf_text.js`, `doc_text.js`, `pdf_parse_text.js`) to guarantee verbatim text parity with `pdfjs-dist` and `word-extractor`. A Node.js runtime (`Node 20+` or `>=18.0.0`) must be installed on the host.
3. **Single Worker Process & Sequential Processing**: The Python service (`uvicorn`) must run with `--workers 1`. Single worker, sequential processing: parsing requests are processed sequentially (e.g. 5 simultaneous requests took 7.5 s total wall time), so `/health` checks can wait during an active parse.
4. **Linux/Docker Untested**: Linux/Docker untested; all Phase 5 parity gates, binary text extractions, and multi-format regressions were validated natively on Windows 11 host.
5. **OCR Lightly Validated**: OCR lightly validated on limited image sets. Native optical character recognition relies on external `tesseract.exe`.
6. **Non-Word PDFs Lightly Tested**: Non-Word PDFs lightly tested; the 108 PDF validation corpus was generated from standard Microsoft Word export filters.
7. **Emoji-in-Skills Quirk**: Emoji-in-skills quirk; leading non-BMP emoji bullets within dedicated skills section lines are captured verbatim as part of skill tokens due to regex matching behavior from the original TypeScript service.
8. **"Present" Dates Use the Local Timezone**: "Present" dates use the local timezone. Date calculations resolving current or open-ended roles reference system local time.
9. **Service Fidelity & Improvements**: Behaviour matches the original service; extraction accuracy improvements are planned as a later version.

---

## Deployment Status Notice

> [!WARNING]
> **Linux/Docker deployment untested**: All Phase 5 binary extraction and parsing parity validations were conducted natively on Windows 11 host. Linux/Docker deployment untested.

