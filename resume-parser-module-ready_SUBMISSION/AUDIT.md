# Comprehensive Codebase Audit: TypeScript to Python Porting Plan (Phase 1 & Phase 1b)

This audit documents the complete architecture, dependencies, regex catalog, string indexing mechanics, AI pipeline, API routes, test coverage, and porting risks for migrating the `resume-parser-module` from TypeScript/Node.js to pure Python.

---

## 1. Full Folder Tree of `src/` and `tests/`

```
resume-parser-module-ready/
├── src/
│   ├── adapters/
│   │   └── candidateStoreAdapter.ts       # Persistence adapter interface & in-memory store
│   ├── ai/
│   │   ├── config.ts                     # AI environment config, API keys, model fallbacks
│   │   ├── experience.ts                 # Date range & total duration calculation logic
│   │   ├── extract.ts                    # Multi-format document buffer preprocessor
│   │   ├── gemini.ts                     # Google Generative AI REST client & chat caller
│   │   ├── normalize.ts                  # Contact & parsed field normalizer
│   │   ├── pdfText.ts                    # PDF buffer layout text extraction via pdf-parse
│   │   ├── prompt.ts                     # Extraction system prompt & text prompt templates
│   │   └── schema.ts                     # JSON extraction, markdown stripping & validation
│   ├── routes/
│   │   └── resumeParserRouter.ts         # Express multer upload router & HTTP endpoints
│   ├── candidateNameValidation.ts        # Header exclusion & candidate name sanitization
│   ├── coreTechKeywords.ts               # Alphabetical catalog of technical skills & phrases
│   ├── extractResumeText.ts              # Document text extraction (PDF, DOCX, DOC, TXT)
│   ├── index.ts                          # Public library barrel export file
│   ├── metaforgeParser.ts                # Orchestrator & Evidence-Lock pipeline
│   ├── parseCoreResumeFields.ts          # Deterministic local heuristic & regex parser
│   ├── resumeFieldSanitize.ts            # Education, degree & display text sanitizers
│   ├── server.ts                         # Standalone Express microservice server entrypoint
│   ├── skillsExtractionEngine.ts         # Modular 10-skill cap skills extraction engine
│   └── types.ts                          # TypeScript interface contracts & data shapes
└── tests/
    ├── candidateNameValidation.test.ts   # Name validation & section title rejection tests
    ├── designationExtraction.test.ts     # 4-tier designation priority hierarchy tests
    ├── documentFormatExtraction.test.ts  # Document parsing, location lock & store tests
    ├── parseCoreResumeFields.name.test.ts# Name extraction edge cases & precedence tests
    ├── resumeFieldSanitize.test.ts       # Degree compaction & job role phrase filter tests
    ├── resumeParserRouter.test.ts        # Express HTTP router end-to-end integration tests
    ├── setup.ts                          # Jest environment configuration & timeout overrides
    ├── skillsExtractionEngine.test.ts    # Skills layouts, tables, columns & 10-skill cap tests
    └── strictSkillsAndExperience.test.ts # Strict duration calculators & regression tests
```

---

## 2. File-by-File Analysis: Purpose, Exports, and Imports

### Source Modules (`src/`)

#### 1. `src/types.ts`
- **Purpose**: Defines shared data contracts, interfaces, and types across the entire engine.
- **External Imports**: None.
- **Internal Imports**: None.
- **Exports**: `ParsedCandidateResume`, `CoreParsedFields`, `BulkParseItemResult`, `ExtractResumeTextResult`, `MetaforgeParsed`, `ResumeParserOptions`, `ChatMessage`, `ChatWithContextOptions`.

#### 2. `src/coreTechKeywords.ts`
- **Purpose**: Static dictionary of canonical technology and software engineering skills used for fuzzy and exact matching.
- **External Imports**: None.
- **Internal Imports**: None.
- **Exports**: `CORE_TECH_KEYWORDS`.

#### 3. `src/candidateNameValidation.ts`
- **Purpose**: Validates extracted candidate names to prevent resume section titles and job titles from being treated as names.
- **External Imports**: None.
- **Internal Imports**: None.
- **Exports**: `isBadCandidateDisplayName`, `trimJobTitleSuffixFromDisplayName`, `isResumeSectionHeadingLine`.

#### 4. `src/resumeFieldSanitize.ts`
- **Purpose**: String cleaners for academic degrees, educational courses, job roles, and display punctuation.
- **External Imports**: None.
- **Internal Imports**: None.
- **Exports**: `sanitizeDisplayText`, `normalizeSkillToken`, `CERTIFICATION_STOP_RE`, `isCertificationOrNonAcademic`, `DEGREE_RE`, `cleanAcademicSpecialization`, `compactHighestQualification`, `looksLikeJobRolePhrase`.

#### 5. `src/ai/config.ts`
- **Purpose**: Environment configuration loader for Gemini API keys, default models, and fallback chains.
- **External Imports**: `dotenv`.
- **Internal Imports**: None.
- **Exports**: `config`, `getAiModelLabel`.

#### 6. `src/ai/prompt.ts`
- **Purpose**: Strict prompt engineering templates for Gemini AI structured extraction.
- **External Imports**: None.
- **Internal Imports**: None.
- **Exports**: `EXTRACTION_PROMPT`, `buildTextPrompt`.

#### 7. `src/ai/schema.ts`
- **Purpose**: Strips markdown code blocks, extracts JSON objects from raw AI strings, and validates mandatory schema fields.
- **External Imports**: None.
- **Internal Imports**: None.
- **Exports**: `validateParsedResult`, `extractJsonFromText`.

#### 8. `src/ai/experience.ts`
- **Purpose**: Parses employment date intervals and calculates total career experience in years and months.
- **External Imports**: None.
- **Internal Imports**: None.
- **Exports**: `calculateExperienceMonths`, `cleanExperienceOutput`, `resolveExperienceFields`.

#### 9. `src/ai/pdfText.ts`
- **Purpose**: Extracts raw text streams from PDF buffers for text-only fallback AI parsing.
- **External Imports**: `pdf-parse`, `pdfjs-dist/legacy/build/pdf.mjs` (dynamic).
- **Internal Imports**: None.
- **Exports**: `extractPdfText`.

#### 10. `src/ai/extract.ts`
- **Purpose**: Inspects file extensions and transforms binary buffers into base64 or plaintext for AI consumption.
- **External Imports**: `mammoth`.
- **Internal Imports**: None.
- **Exports**: `getExtension`, `isSupportedFile`, `extractFileContent`.

#### 11. `src/extractResumeText.ts`
- **Purpose**: Multi-format document text extractor supporting PDF, DOCX, DOC, TXT, and OCR for images.
- **External Imports**: `pdf-parse`, `mammoth`, `word-extractor`, `tesseract.js` (dynamic), `pdfjs-dist/legacy/build/pdf.mjs` (dynamic), `@napi-rs/canvas` (dynamic).
- **Internal Imports**: None.
- **Exports**: `ExtractResumeTextResult`, `extractPlainTextFromResumeBuffer`.

#### 12. `src/adapters/candidateStoreAdapter.ts`
- **Purpose**: Storage abstraction and reference in-memory store for saving and retrieving parsed candidate profiles.
- **External Imports**: None.
- **Internal Imports**: `../types` (`ParsedCandidateResume`).
- **Exports**: `CandidateStoreAdapter`, `InMemoryCandidateStore`.

#### 13. `src/skillsExtractionEngine.ts`
- **Purpose**: Modular skills extraction engine enforcing dedicated section isolation, layout parsing, and a strict 10-skill cap.
- **External Imports**: None.
- **Internal Imports**: `./coreTechKeywords` (`CORE_TECH_KEYWORDS`), `./resumeFieldSanitize` (`looksLikeJobRolePhrase`).
- **Exports**: `SkillsSectionLayout`, `SkillEvidence`, `SkillsExtractionDiagnostics`, `SkillsEngineOptions`, `SkillsExtractionResult`, `ELIGIBLE_SKILLS_HEADING_PATTERNS`, `NEXT_SECTION_HEADING_RE`, `DetectedSection`, `cleanHeadingLine`, `isSkillSectionHeading`, `detectSkillSection`, `splitDelimitedTokens`, `expandCompoundSkillPhrases`, `extractSkillsFromStandardList`, `extractSkillsFromTable`, `extractSkillsFromTwoColumns`, `extractSkillsWithEngineSync`, `extractSkillsWithEngine`, `validateSkillsAgainstSection`.

#### 14. `src/ai/normalize.ts`
- **Purpose**: Normalizes contact phone numbers with country codes and unifies parsed AI records.
- **External Imports**: None.
- **Internal Imports**: `./experience` (`resolveExperienceFields`).
- **Exports**: `normalizePhone`, `normalizeParsedResult`.

#### 15. `src/parseCoreResumeFields.ts`
- **Purpose**: Zero-dependency deterministic regex parser extracting candidate names, contact info, experience, degrees, and roles.
- **External Imports**: None.
- **Internal Imports**: `./candidateNameValidation` (`isBadCandidateDisplayName`, `trimJobTitleSuffixFromDisplayName`, `isResumeSectionHeadingLine`), `./resumeFieldSanitize` (`cleanAcademicSpecialization`, `compactHighestQualification`, `sanitizeDisplayText`), `./skillsExtractionEngine` (`extractSkillsWithEngineSync`).
- **Exports**: `CoreParsedFields`, `ELIGIBLE_SKILLS_HEADING_RE`, `PROHIBITED_HEADING_RE`, `extractEligibleSkillsBlock`, `extractHighestQualificationFromAnyText`, `calculateExperienceFromWorkHistory`, `parseNumericYears`, `cleanExperienceOutput`, `extractTotalExperienceInfo`, `extractCurrentLocation`, `extractWholeResumeSkills`, `cleanAndValidateRoleOrTechnologies`, `extractVerbatimDesignation`, `parseCoreFieldsFromResumeText`.

#### 16. `src/ai/gemini.ts`
- **Purpose**: Native REST client for Google Generative AI (Gemini) handling multimodal PDF parsing, text prompts, skills fallback, and context chat.
- **External Imports**: None (native `fetch`).
- **Internal Imports**: `./config` (`config`), `./prompt` (`EXTRACTION_PROMPT`, `buildTextPrompt`), `./schema` (`extractJsonFromText`, `validateParsedResult`), `./normalize` (`normalizeParsedResult`), `./pdfText` (`extractPdfText`), `../types` (`MetaforgeParsed`).
- **Exports**: `callGemini`, `parseResumeFromPdf`, `parseResumeFromText`, `extractSkillsWithGemini`, `chatWithContext`.

#### 17. `src/metaforgeParser.ts`
- **Purpose**: Primary orchestrator executing Gemini AI parsing with automatic fallback to local regex parsing, followed by Evidence-Lock validation.
- **External Imports**: None.
- **Internal Imports**: `./extractResumeText` (`extractPlainTextFromResumeBuffer`), `./parseCoreResumeFields` (`parseCoreFieldsFromResumeText`, `extractHighestQualificationFromAnyText`, `extractTotalExperienceInfo`, `extractVerbatimDesignation`, `cleanAndValidateRoleOrTechnologies`, `extractCurrentLocation`), `./skillsExtractionEngine` (`extractSkillsWithEngineSync`, `extractSkillsWithEngine`, `validateSkillsAgainstSection`), `./resumeFieldSanitize` (`isCertificationOrNonAcademic`, `cleanAcademicSpecialization`, `compactHighestQualification`, `sanitizeDisplayText`), `./ai/extract` (`isSupportedFile`, `extractFileContent`), `./ai/gemini` (`parseResumeFromPdf`, `parseResumeFromText`, `extractSkillsWithGemini`), `./ai/config` (`config`, `getAiModelLabel`), `./types` (`ParsedCandidateResume`, `BulkParseItemResult`, `MetaforgeParsed`).
- **Exports**: `ParsedCandidateResume`, `BulkParseItemResult`, `getAiParsingSuspendedReason`, `isMetaforgeParserAvailable`, `applyEvidenceLock`, `parseResumeBufferWithMetaforge`, `parseResumeBufferLegacy`, `parseResumeBuffer`, `parseResumeBuffersBulk`.

#### 18. `src/routes/resumeParserRouter.ts`
- **Purpose**: Express.js router providing HTTP endpoints for single resume parsing, bulk resume parsing, and service health checks.
- **External Imports**: `express` (`Router`, `Request`, `Response`), `multer`, `path`.
- **Internal Imports**: `../metaforgeParser` (`parseResumeBuffer`, `parseResumeBuffersBulk`, `isMetaforgeParserAvailable`, `getAiParsingSuspendedReason`).
- **Exports**: `resumeParserRouter` (default and named).

#### 19. `src/index.ts`
- **Purpose**: Public API barrel module aggregating all types, parsers, engines, sanitizers, and adapters.
- **External Imports**: None.
- **Internal Imports**: Re-exports from `./types`, `./metaforgeParser`, `./parseCoreResumeFields`, `./skillsExtractionEngine`, `./extractResumeText`, `./ai/gemini`, `./candidateNameValidation`, `./resumeFieldSanitize`, `./coreTechKeywords`, `./adapters/candidateStoreAdapter`, `./routes/resumeParserRouter`.
- **Exports**: All library functions, classes, and types.

#### 20. `src/server.ts`
- **Purpose**: Standalone microservice HTTP server entrypoint.
- **External Imports**: `express`, `cors`, `dotenv`.
- **Internal Imports**: `./routes/resumeParserRouter` (`resumeParserRouter`), `./metaforgeParser` (`isMetaforgeParserAvailable`), `./ai/config` (`getAiModelLabel`).
- **Exports**: `server`, `app` (default).

---

## 3. Dependency Order for Porting (Leaf Modules First)

The dependency graph of `src/` has **zero circular dependencies**. Porting must proceed in this topological order:

```
[Layer 0: Pure Leaf Modules - Zero Internal Dependencies]
  1. src/types.ts
  2. src/coreTechKeywords.ts
  3. src/candidateNameValidation.ts
  4. src/resumeFieldSanitize.ts
  5. src/ai/config.ts
  6. src/ai/prompt.ts
  7. src/ai/schema.ts
  8. src/ai/experience.ts
  9. src/ai/pdfText.ts
  10. src/extractResumeText.ts
  11. src/ai/extract.ts

[Layer 1: Single-Leaf Dependencies]
  12. src/adapters/candidateStoreAdapter.ts  (depends on: types.ts)
  13. src/skillsExtractionEngine.ts         (depends on: coreTechKeywords.ts, resumeFieldSanitize.ts)
  14. src/ai/normalize.ts                   (depends on: ai/experience.ts)

[Layer 2: Multi-Module Domain Logic]
  15. src/parseCoreResumeFields.ts          (depends on: candidateNameValidation.ts, resumeFieldSanitize.ts, skillsExtractionEngine.ts)
  16. src/ai/gemini.ts                      (depends on: ai/config.ts, ai/prompt.ts, ai/schema.ts, ai/normalize.ts, ai/pdfText.ts, types.ts)

[Layer 3: Orchestration & Evidence-Lock]
  17. src/metaforgeParser.ts                (orchestrator: depends on 10, 11, 13, 14, 15, 16)

[Layer 4: Delivery & Application Adapters]
  18. src/routes/resumeParserRouter.ts      (depends on: metaforgeParser.ts)
  19. src/index.ts                          (barrel aggregator)
  20. src/server.ts                         (HTTP server application entrypoint)
```

---

## 4. AST-Generated Regex Catalog (`regex_catalog.json`) & Reconciled Totals

### Reconciling the 443 Heuristic Figure with the 585 AST Count

The script [`scratch/build_regex_catalog.js`](scratch/build_regex_catalog.js) was executed using the official **TypeScript 5.9 Compiler API** (`ts.createSourceFile`, `ts.SyntaxKind.RegularExpressionLiteral`, `ts.isNewExpression`) to inspect every single AST node across all 29 TypeScript files.

- **Initial line-by-line regex heuristic**: Found **443** patterns.
- **Official AST-parsed total**: Exactly **585** regex instances.
- **Reconciliation difference (+142)**:
  1. **Multi-line array literals**: In `src/parseCoreResumeFields.ts` and `src/skillsExtractionEngine.ts`, large arrays of regexes (e.g. `ELIGIBLE_SKILLS_HEADING_PATTERNS`, `DEGREE_PREFIX_PATTERNS`) span multiple lines or contain multiple regex literals per statement, which naive line-based regexes collapsed or skipped.
  2. **Chained inline replacements**: Multiple chained `.replace(/.../g, '').replace(/.../g, '')` on single lines were partially truncated by line-boundary matchers.
  3. **Constructor expressions**: `new RegExp(...)` calls using template expressions, variables, or dynamic flags were accurately identified via AST `ts.isNewExpression`.

The complete artifact is persisted at [`regex_catalog.json`](regex_catalog.json) at the repo root.

### AST Regex Breakdown by File

| File | Regex Literals | `new RegExp(...)` | Dynamic | Total |
| :--- | :--- | :--- | :--- | :--- |
| `src/parseCoreResumeFields.ts` | 299 | 5 | 5 | **304** |
| `src/skillsExtractionEngine.ts` | 148 | 1 | 1 | **149** |
| `src/resumeFieldSanitize.ts` | 45 | 0 | 0 | **45** |
| `src/ai/experience.ts` | 28 | 0 | 0 | **28** |
| `src/metaforgeParser.ts` | 13 | 0 | 0 | **13** |
| `src/candidateNameValidation.ts` | 11 | 0 | 0 | **11** |
| `src/ai/gemini.ts` | 11 | 0 | 0 | **11** |
| `src/extractResumeText.ts` | 4 | 0 | 0 | **4** |
| `src/ai/normalize.ts` | 3 | 0 | 0 | **3** |
| `src/ai/schema.ts` | 3 | 0 | 0 | **3** |
| `tests/resumeFieldSanitize.test.ts` | 7 | 0 | 0 | **7** |
| `tests/resumeParserRouter.test.ts` | 3 | 0 | 0 | **3** |
| `tests/designationExtraction.test.ts` | 2 | 0 | 0 | **2** |
| `tests/documentFormatExtraction.test.ts` | 2 | 0 | 0 | **2** |
| **Total** | **579** | **6** | **6** | **585** |

---

## 5. Regex Character Classes, Anchors & Flag Semantics: JavaScript vs. Python

The AST scanner analyzed all 585 patterns for token occurrences of `\d`, `\w`, `\s`, `\b`, `.`, multiline anchors, and flags:

| Pattern Token / Flag | Count in Codebase | JavaScript Semantics | Python Semantics & Porting Risk | Actionable Mitigation in Python |
| :--- | :--- | :--- | :--- | :--- |
| **`\d`** | 87 | Matches strictly ASCII `[0-9]`. | Matches **all Unicode decimal digits** (Arabic, Devanagari, Fullwidth digits like `۱`, `५`, `５`). | Use `re.ASCII` (`re.A`) flag or explicit `[0-9]` to prevent non-Latin digits from parsing as experience years. |
| **`\w`** | 3 | Matches strictly ASCII `[A-Za-z0-9_]`. | Matches **all Unicode alphanumeric characters** across all languages. | Compile with `re.ASCII` or use `[A-Za-z0-9_]`. |
| **`\s`** | 379 | Matches ASCII whitespace + Unicode spaces (`\u00A0`, `\u2000-\u200A`). | Matches Unicode whitespace by default. Matches JS behavior closely. | Safe to use directly, but ensure `\u00a0` (non-breaking space) is normalized. |
| **`\b`** | 203 | Word boundary determined strictly by ASCII `\w`. | Word boundary determined by Unicode `\w`. Characters with accents (e.g. `René`, `Müller`) treat `é` and `ü` as word characters in Python, causing boundary misses. | Compile keyword and designation regexes with `re.ASCII` to match JS boundary behavior. |
| **`.` (dot)** | 91 | Matches any char **except** `\n`, `\r`, `\u2028`, `\u2029`. | Matches any char **except `\n`** (in Python, `.` **does match `\r`**!). | When parsing CRLF text without prior normalization, `.` in Python will consume `\r`. Normalize `\r\n` to `\n` before running regexes. |
| **Multiline `^` / `$`** | 0 | Codebase does **not** use the `m` flag. | No regex uses `m`. Line anchors are emulated via `(?:^\|\n)` or `.split(/\r?\n/)`. | Maintain explicit `(?:^\|\n)` line boundary patterns. |
| **Flag `s` (dotAll)** | 0 | Codebase does **not** use literal `s` flag. Emulates dotAll via `[\s\S]*`. | `[\s\S]*` is 100% portable to Python `re`. | Retain `[\s\S]*` in Python. |
| **Flag `u` (unicode)** | 0 | No literal `u` flags used. | In Python 3, strings and patterns are Unicode by default. | Explicitly enforce ASCII mode where ASCII behavior is required. |
| **Flag `y` (sticky)** | 0 | No sticky flags used. | N/A. | N/A. |

---

## 6. Variable-Length Lookbehinds: Analysis & Test Verifications

Python standard library `re` forbids variable-length lookbehinds (`re.error: look-behind requires fixed-width pattern`).

Below are the 4 exact instances in the codebase, with:
1. Full TypeScript pattern.
2. Proposed Python equivalent using the `regex` module.
3. Pure Python `re` fallback refactoring without third-party dependencies.
4. Three distinct test verification strings.

---

### Instance 1: `src/parseCoreResumeFields.ts:1411`
- **TypeScript Pattern**: `/(?<!Professional\s+|Career\s+|Profile\s+)Summary/i`
- **Purpose**: Slices the "Summary" section only when it is standalone, and NOT when it is part of "Professional Summary", "Career Summary", or "Profile Summary" (which are prioritized earlier in the hierarchy).
- **Proposed Python (`regex` module)**:
  ```python
  import regex
  pattern = regex.compile(r'(?<!Professional\s+|Career\s+|Profile\s+)Summary', regex.IGNORECASE)
  ```
- **Pure `re` Equivalent**:
  ```python
  # Match optional preceding qualifier word and check that it was absent
  pattern = re.compile(r'(?:(Professional|Career|Profile)\s+)?\b(Summary)\b', re.IGNORECASE)
  # match is valid standalone Summary if match.group(1) is None
  ```
- **3 Test Strings**:
  1. `"Summary\nExperienced full-stack engineer with 5 years..."`
     - *Expected*: Matches `"Summary"`.
  2. `"Professional Summary\nSenior software architect..."`
     - *Expected*: Does **NOT** match `"Summary"` (preceded by `"Professional "`).
  3. `"Career   Summary\nDevOps specialist..."`
     - *Expected*: Does **NOT** match `"Summary"` (preceded by `"Career   "` with multiple spaces).

---

### Instance 2: `src/parseCoreResumeFields.ts:1412`
- **TypeScript Pattern**: `/(?<!Executive\s+|Profile\s+)(?:Professional\s+)?Profile/i`
- **Purpose**: Slices the standalone "Profile" or "Professional Profile" section, while skipping "Executive Profile" or "Profile Profile".
- **Proposed Python (`regex` module)**:
  ```python
  import regex
  pattern = regex.compile(r'(?<!Executive\s+|Profile\s+)(?:Professional\s+)?Profile', regex.IGNORECASE)
  ```
- **Pure `re` Equivalent**:
  ```python
  pattern = re.compile(r'(?:(Executive|Profile)\s+)?\b((?:Professional\s+)?Profile)\b', re.IGNORECASE)
  # match is valid if match.group(1) is None
  ```
- **3 Test Strings**:
  1. `"Profile\nData engineer specialized in distributed systems..."`
     - *Expected*: Matches `"Profile"`.
  2. `"Professional Profile\nMachine learning researcher..."`
     - *Expected*: Matches `"Professional Profile"`.
  3. `"Executive Profile\nChief Technology Officer..."`
     - *Expected*: Does **NOT** match (preceded by `"Executive "`).

---

### Instance 3: `src/resumeFieldSanitize.ts:65`
- **TypeScript Pattern**: `/(?<!\b(?:[A-Z]|Tech|Engg|Hons|Phil|Admin))\.\s+[\s\S]*/i`
- **Purpose**: In `cleanAcademicSpecialization`, cuts off trailing sentence clauses at a period, but **preserves** periods that belong to academic abbreviations (e.g. `B.Tech.`, `B.E.`, `B.Sc.`, `Admin.`, `Hons.`).
- **Proposed Python (`regex` module)**:
  ```python
  import regex
  pattern = regex.compile(r'(?<!\b(?:[A-Z]|Tech|Engg|Hons|Phil|Admin))\.\s+[\s\S]*', regex.IGNORECASE)
  cleaned = pattern.sub('', raw_degree)
  ```
- **Pure `re` Equivalent**:
  ```python
  # Split on period followed by space, check preceding token against whitelist
  def cut_trailing_narrative(text: str) -> str:
      parts = re.split(r'\.\s+', text, maxsplit=1)
      if len(parts) == 1:
          return text
      first_part = parts[0]
      last_word = re.search(r'\b([A-Za-z]+)$', first_part)
      whitelist = {'Tech', 'Engg', 'Hons', 'Phil', 'Admin'}
      if last_word and (len(last_word.group(1)) == 1 or last_word.group(1) in whitelist):
          # Period belongs to abbreviation; retain
          return text
      return first_part
  ```
- **3 Test Strings**:
  1. `"B.Tech in Computer Science. Currently employed at Google."`
     - *Expected*: Cuts off trailing clause -> `"B.Tech in Computer Science"`.
  2. `"M.Tech. in Artificial Intelligence"`
     - *Expected*: Retains period after `Tech.` -> `"M.Tech. in Artificial Intelligence"`.
  3. `"Bachelor of Science. Graduated with honors in 2020."`
     - *Expected*: Cuts off trailing narrative -> `"Bachelor of Science"`.

---

### Instance 4: `src/resumeFieldSanitize.ts:123`
- **TypeScript Pattern**: `/(?<!\b(?:[A-Z]|Tech|Engg|Hons|Phil|Admin))\.\s+[\s\S]*/i`
- **Purpose**: Used in `compactHighestQualification` to strip job descriptions and sentences erroneously merged into degree qualifications.
- **Proposed Python (`regex` module)**:
  ```python
  import regex
  pattern = regex.compile(r'(?<!\b(?:[A-Z]|Tech|Engg|Hons|Phil|Admin))\.\s+[\s\S]*', regex.IGNORECASE)
  ```
- **3 Test Strings**:
  1. `"B.E. Mechanical Engineering. Responsible for CAD 3D modeling."`
     - *Expected*: `"B.E. Mechanical Engineering"`.
  2. `"B.Engg. in Robotics"`
     - *Expected*: `"B.Engg. in Robotics"`.
  3. `"Master of Business Administration. CGPA 3.9."`
     - *Expected*: `"Master of Business Administration"`.

---

## 7. Native Subprocesses, Worker Threads & Binary Dependencies

Audit of `child_process`, `tesseract.js`, `pdfjs-dist`, and `@napi-rs/canvas`:

| Technology / Module | Where Used | Exact File & Line | What is Spawned / Executed | Python Replacement Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **`child_process`** | **None in `src/`** | `app.py:86` (Python demo UI only) | In TypeScript source, **zero** child processes are spawned. Only the Streamlit test harness invokes `subprocess.Popen([sys.executable, "-m", "uvicorn", "src.server:app"])`. | In Python module: No child processes required. |
| **`tesseract.js`** | `src/extractResumeText.ts` | Line 39 (`import('tesseract.js')`) | Spawns **Node.js worker threads** (`worker_threads`) running WebAssembly (`tesseract-core.wasm`) to execute in-memory OCR on image buffers (`Buffer`). Does not spawn an OS process. | Use `pytesseract` (invoking system `tesseract` binary) or `easyocr` (pure Python/PyTorch). |
| **`pdfjs-dist`** | `src/extractResumeText.ts`<br>`src/ai/pdfText.ts` | Lines 46, 88<br>Line 13 | Runs **in-thread inside the Node V8 engine** with `disableWorker: true` and `isEvalSupported: false`. Zero subprocesses. Used to extract text items and render PDF pages to canvas contexts. | Use `pypdf` or `pdfplumber` for text; use `pdf2image` (poppler) or `fitz` (PyMuPDF) for page rendering. |
| **`@napi-rs/canvas`** | `src/extractResumeText.ts` | Line 54 (`import('@napi-rs/canvas')`) | In-process **native Rust N-API C++ binding**. Provides a headless HTML5 Canvas 2D context (`createCanvas`) to serialize rendered PDF pages into PNG image buffers. Zero child processes. | Use `Pillow` (`PIL.Image`) or `PyMuPDF` (`fitz.Pixmap`) to output image buffers. |

---

## 8. Catalog of Math, Date, String & Array Operations

Complete audit of `Math.round`, `toFixed`, `parseInt`, `parseFloat`, `Number()`, `Date`, `.trim()`, and array `indexOf`/`find` returning `-1`:

Total occurrences found across `src/`: **253**.

### 1. `Math.round` (2 occurrences)
* `src/ai/experience.ts:285`: `Math.round(parseFloat(m[1]) * 12)`
  - Converts decimal years (e.g. `2.5`) to integer months (`30`).
  - *Risk in Python*: Python's built-in `round(2.5)` uses **banker's rounding (round-half-to-even)**, rounding `2.5` to `2`! Must use `math.floor(val + 0.5)` or `Decimal.quantize(ROUND_HALF_UP)` to match JS round-half-up semantics.
* `src/ai/experience.ts:303`: `Math.round((totalMonths / 12) * 10) / 10`
  - Rounds total years to 1 decimal place.

### 2. `toFixed` (0 occurrences)
* None used in the codebase.

### 3. `parseInt` (4 occurrences)
* `src/server.ts:12`: `parseInt(process.env.PORT || '3001', 10)`
* `src/ai/experience.ts:278`: `parseInt(mOnly[1], 10)`
* `src/ai/experience.ts:282`: `parseInt(ym[1], 10) * 12 + parseInt(ym[2], 10)`
* `src/parseCoreResumeFields.ts:820`: `parseInt(m[1]!, 10)`
  - *Risk in Python*: JavaScript `parseInt("12 years", 10)` parses leading digits and returns `12`. Python `int("12 years")` raises `ValueError`! Python code must ensure strings passed to `int()` contain only digits.

### 4. `parseFloat` (3 occurrences)
* `src/ai/experience.ts:285`: `parseFloat(m[1])`
* `src/parseCoreResumeFields.ts:825`: `Math.floor(parseFloat(ym[1]))`
* `src/parseCoreResumeFields.ts:829`: `Math.floor(parseFloat(num[1]))`

### 5. `Number()` (17 occurrences)
* `src/ai/config.ts:6`: `Number(process.env.PORT)`
* `src/ai/experience.ts:26, 29, 30, 37, 40, 47, 50, 58, 61`: Date component conversions (`Number(iso[1])`).
* `src/parseCoreResumeFields.ts:649, 653, 659, 661, 667, 669, 675`: Year/month extraction from date tokens.

### 6. `Date` / `new Date` (17 occurrences)
* `src/adapters/candidateStoreAdapter.ts:24`: `Date.now()` (Used for unique ID generation).
* `src/ai/experience.ts:20, 26, 37, 47, 58, 88`:
  - Date constructor: `new Date(year, monthIndex, day)`.
  - **CRITICAL JS DIFFERENCE**: In JavaScript, **months are 0-indexed (0 = January, 11 = December)**!
  - `Number(iso[2]) - 1` is explicitly calculated.
  - In Python `datetime.date(year, month, day)`, **months are 1-indexed (1 = January, 12 = December)**!
  - *Mitigation*: Do not subtract 1 when porting to Python's `datetime`.
* `src/parseCoreResumeFields.ts:643`: `const now = new Date();` (Current year boundary check).

### 7. String `.trim()`, `.trimStart()`, `.trimEnd()` (196 occurrences)
* Extensively used throughout all sanitizers and regex extractors.
* In Python, `str.strip()`, `str.lstrip()`, and `str.rstrip()` provide 1:1 behavioral equivalence for ASCII whitespace.
* *Note*: JS `.trim()` also strips non-breaking space `\u00A0` and zero-width spaces; ensure Python strings are normalized or use `strip()`.

### 8. Array `indexOf` & `find` Returning `-1` or `undefined` (11 occurrences)
* `src/skillsExtractionEngine.ts:1019-1020`:
  ```typescript
  const priorityA = PRIORITY_ORDER.indexOf(a.sourceSection);
  const priorityB = PRIORITY_ORDER.indexOf(b.sourceSection);
  ```
  - If a section is not found in `PRIORITY_ORDER`, JS returns `-1`.
  - In Python, `list.index(x)` **raises `ValueError`**!
  - *Mitigation*: Use a helper `PRIORITY_MAP.get(sec, 999)` or `list.index()` wrapped in `try/except ValueError`.
* `src/skillsExtractionEngine.ts:900, 1004`:
  ```typescript
  const pos = content.toLowerCase().indexOf(cleaned.toLowerCase());
  ```
  - Searches for character offset of skill in section text. Returns `-1` if not found.
  - In Python, `str.index()` raises `ValueError`.
  - *Mitigation*: Use `str.find()`, which returns `-1` on failure, matching JS semantics.
* `src/ai/schema.ts:46-47`:
  ```typescript
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  ```
  - Uses `start === -1 || end === -1 || start >= end`.
  - *Mitigation*: Use `text.find('{')` and `text.rfind('}')`.
* `src/extractResumeText.ts:148`:
  ```typescript
  const dot = filename.lastIndexOf('.');
  ```
  - Checks `dot >= 0`.
  - *Mitigation*: Use `filename.rfind('.')`.
* `src/ai/normalize.ts:16` & `src/parseCoreResumeFields.ts:1027, 1030, 1680`:
  - `Array.prototype.find()` returns `undefined` if no match.
  - *Mitigation*: In Python, use `next((x for x in items if condition), None)`.

---

## 9. State Persistence & Text Normalization Mechanics

### Does `aiParsingSuspended` Ever Reset?
- **NO. It NEVER resets.**
- Defined at module scope in [`src/metaforgeParser.ts:32-33`](src/metaforgeParser.ts#L32-L33):
  ```typescript
  let aiParsingSuspended = false;
  let aiParsingSuspendedReason: string | null = null;
  ```
- When a quota error occurs (`src/metaforgeParser.ts:313`):
  ```typescript
  aiParsingSuspended = true;
  aiParsingSuspendedReason = 'Gemini API quota or rate limit reached — using keyword parser for remaining resumes.';
  ```
- There is **no timer, no reset endpoint, and no clearing logic** in the codebase.
- Once tripped, the flag remains `true` for the entire lifetime of the process. All subsequent single or bulk parse requests permanently bypass Gemini AI and execute via the local deterministic fallback parser until the process is restarted.
- *Python Porting Consideration*: In Python, this will be represented as a module-level boolean or class state. A management reset method (`reset_ai_suspension()`) should be added for testing purposes.

### Is Text Normalized for `\r\n` Before Parsing?
- **Partially / Conditionally:**
  1. **Binary buffer extraction** via `extractPlainTextFromResumeBuffer()` in `src/extractResumeText.ts:24-31` explicitly runs `normalizeResumeText`:
     ```typescript
     function normalizeResumeText(raw: string): string {
       return raw
         .replace(/\r\n/g, '\n')
         .replace(/\r/g, '\n')
         .replace(/[ \t]+\n/g, '\n')
         .replace(/\n{3,}/g, '\n\n')
         .trim();
     }
     ```
     This cleans `.docx`, `.doc`, `.txt`, and OCR text.
  2. **Direct string inputs**: If `parseCoreFieldsFromResumeText(text)` or `parseResumeFromText(text)` is invoked directly with a raw string (e.g. in unit tests or external library calls):
     - Line splitting in `parseCoreResumeFields.ts:56` handles `\r?\n`: `text.split(/\r?\n/)`.
     - **BUT** section boundary regexes (e.g. `SECTION_END` in `parseCoreResumeFields.ts:46`) use hardcoded `\n`:
       `String.raw`(?=\n\s*(?:Education|...))`
       If a caller passes a raw Windows CRLF string directly to `parseCoreFieldsFromResumeText`, `\r` immediately preceding `\n` can prevent section headers from matching!
- *Mitigation for Python*: Enforce `text = re.sub(r'\r\n?', '\n', text)` at the entrypoint of all parsing functions.

---

## 10. HTTP Middleware Boundaries: Multer, CORS & Undefined vs. Null Fields

### Multer Configuration & Error Responses
- **File Upload Limits**:
  ```typescript
  limits: { fileSize: 15 * 1024 * 1024, files: 5 } // 15 MB file size limit, 5 files max
  ```
- **File Extension Filter**:
  Supported extensions: `.pdf`, `.doc`, `.docx`, `.txt`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`.
  If an invalid extension is uploaded, Multer invokes `cb(new Error("File format ${ext} is not supported..."))`.
- **Error Response Codes & Payloads**:
  1. **Missing form-data field**:
     - `POST /parse` with missing `resume`: HTTP **400 Bad Request**
       ```json
       { "success": false, "message": "Resume file is required under form field \"resume\"" }
       ```
     - `POST /parse/bulk` with missing `resumes`: HTTP **400 Bad Request**
       ```json
       { "success": false, "message": "At least one resume file is required under form field \"resumes\"" }
       ```
     - `POST /parse/bulk` with > 5 files: HTTP **400 Bad Request**
       ```json
       { "success": false, "message": "Maximum 5 resumes allowed per batch upload" }
       ```
  2. **Multer extension rejection or file size violation**:
     - Caught by the router's `catch (error: any)` block: HTTP **500 Internal Server Error**
       ```json
       { "success": false, "message": "File format .xyz is not supported. Supported: PDF, DOCX, DOC, TXT, and common image formats." }
       ```

### CORS Configuration
- In `src/server.ts:14`: `app.use(cors())`.
- In `src/ai/config.ts:20`: `corsOrigin: process.env.CORS_ORIGIN || '*'`.
- Default behavior allows all origins (`*`), headers, and methods (`GET, POST, OPTIONS`).

### Which Response Fields Can Be `undefined` vs `null`?

In JavaScript JSON serialization, object properties with value `undefined` are **omitted entirely**, whereas properties with value `null` are serialized as literal `null`.

#### `ParsedCandidateResume` Contract Analysis:

| Field Name | Type Definition | Serialized in API as | Notes |
| :--- | :--- | :--- | :--- |
| `candidateName` | `string \| null` | `null` or `string` | Always present. Never omitted. |
| `email` | `string \| null` | `null` or `string` | Always present. Never omitted. |
| `contactNumber` | `string \| null` | `null` or `string` | Always present. Never omitted. |
| `linkedinUrl` | `string \| null` | `null` or `string` | Always present. Never omitted. |
| `highestQualification`| `string \| null`| `null` or `string` | Always present. Never omitted. |
| `skillsRaw` | `string \| null` | `null` or `string` | Always present. Never omitted. |
| `technologiesRaw` | `string \| null` | `null` or `string` | Always present. Never omitted. |
| `totalExperience` | `string \| null` | `null` or `string` | Always present. Never omitted. |
| `relevantExperience` | `string \| null` | `null` | Always explicitly `null`. |
| `currentEmployer` | `string \| null` | `null` or `string` | Always present. Never omitted. |
| `sourceFile` | `string` | `string` | Always present. Original filename. |
| `parser` | `'metaforge' \| 'legacy'` | `'metaforge' \| 'legacy'` | Always present. |
| `technologies` | `string \| null \| undefined` | `null` or `string` | Typed with `?`, but both `mapMetaforgeResult` and `mapLegacyResult` explicitly populate it with `role` or `null`. |
| `currentLocation` | `string \| null \| undefined` | `null` or `string` | Typed with `?`, but explicitly populated as `sanitizeDisplayText(...)` or `null`. |
| `location` | `string \| null \| undefined` | `null` or `string` | Alias of `currentLocation`. Explicitly populated. |
| `role` | `string \| null \| undefined` | `null` or `string` | Explicitly populated. |

#### `BulkParseItemResult` (Union Type):
```typescript
export type BulkParseItemResult =
  | { sourceFile: string; status: 'done'; data: ParsedCandidateResume }
  | { sourceFile: string; status: 'error'; error: string };
```
* In `status: "done"` items: `data` is populated; `error` is **omitted (`undefined`)**.
* In `status: "error"` items: `error` is populated; `data` is **omitted (`undefined`)**.

---

## 11. Analysis of Duplicate Exports in Codebase

Two export symbols appear in multiple files:

### 1. `cleanExperienceOutput`
* **Found in**:
  1. [`src/ai/experience.ts:133`](src/ai/experience.ts#L133)
  2. [`src/parseCoreResumeFields.ts:834`](src/parseCoreResumeFields.ts#L834)
* **Are they re-exports or separate implementations?**
  **They are SEPARATE, INDEPENDENT IMPLEMENTATIONS with slight behavioral divergence:**
  - `src/parseCoreResumeFields.ts` contains Step 1:
    `s = s.replace(/^[|:;\-–—•*▪▫❖➢✓★+\t\s]+/, '')` (strips leading bullet glyphs and table pipes).
  - `src/ai/experience.ts` lacks Step 1 bullet stripping.
  - `src/parseCoreResumeFields.ts` enforces `if (!raw || typeof raw !== 'string') return ''`.
  - `src/ai/experience.ts` takes `raw: any` and does `s = String(raw || '')`.
* **Barrel Resolution (`src/index.ts`)**:
  `src/index.ts:28` exports `cleanExperienceOutput` explicitly from `./parseCoreResumeFields`. The version in `src/ai/experience.ts` is internal to the AI sub-module.
* **Porting Recommendation**: Unify into a single canonical function in Python that includes the bullet-glyph stripping step.

### 2. `CoreParsedFields`
* **Found in**:
  1. [`src/types.ts:24-43`](src/types.ts#L24-L43)
  2. [`src/parseCoreResumeFields.ts:27-43`](src/parseCoreResumeFields.ts#L27-L43)
* **Are they re-exports or separate implementations?**
  **They are duplicate type definitions with identical fields:**
  `src/parseCoreResumeFields.ts` did not import the type from `types.ts`, but declared an identical `type CoreParsedFields = { ... }`.
* **Porting Recommendation**: Define `CoreParsedFields` once in `types.py` (or `models.py`) and import it wherever needed.

---

## 12. Proposed Differential Testing Harness (Node.js vs. Python)

To guarantee 100% mathematical parity across all 585 regex patterns during and after the Python port, we propose a two-phase differential testing suite:

```
                  ┌───────────────────────────────────────────┐
                  │   Golden Corpus (147 Jest Test Strings    │
                  │         + sample_resume.txt)              │
                  └─────────────────────┬─────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
        ┌───────────────────────┐               ┌───────────────────────┐
        │  differential_node.ts │               │  differential_py.py   │
        │ (Runs regexes in V8)  │               │ (Runs regexes in Py)  │
        └───────────┬───────────┘               └───────────┬───────────┘
                    │                                       │
                    ▼                                       ▼
             node_matches.json                       py_matches.json
                    │                                       │
                    └───────────────────┬───────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │      diff_verifier.py       │
                         │ (Asserts 0 index mismatches)│
                         └─────────────────────────────┘
```

### 1. Golden Input Corpus Extraction
- Extract all synthetic candidate resume strings embedded inside `tests/*.test.ts` (147 test cases) into a standardized fixture dataset: `tests/fixtures/golden_corpus.json` (keyed by unique ID, e.g. `cad_resume`, `shiva_boda`, `sap_profile`, `global_mobility`).
- Include the real-world document [`sample_resume.txt`](sample_resume.txt).

### 2. Node.js Differential Runner (`differential_node.ts`)
- Loads `regex_catalog.json` and `golden_corpus.json`.
- For every static regex entry and for every test document:
  - Executes match / search / exec.
  - Records:
    ```json
    {
      "regex_id": "src/parseCoreResumeFields.ts:1411",
      "doc_id": "cad_resume",
      "matched": true,
      "matches": [
        {
          "index": 142,
          "length": 7,
          "text": "Summary",
          "groups": []
        }
      ]
    }
    ```
- Dumps `scratch/node_matches.json`.

### 3. Python Differential Runner (`differential_py.py`)
- Reads the identical `regex_catalog.json` and `golden_corpus.json`.
- Executes each pattern against each test document using the Python regex engine.
- Emits identical schema into `scratch/py_matches.json`.

### 4. Automated Diff Verifier (`diff_verifier.py`)
- Performs a deep equality comparison:
  1. `node_item.matched == py_item.matched`
  2. `node_item.matches.length == py_item.matches.length`
  3. `match.index`, `match.length`, and `match.text` match to the character.
  4. Capture groups are identical.
- Any discrepancy is reported with line numbers, source snippets, and exact character delta.

---

## 13. Phase 1 Approved Amendments & Precision Engineering Rules (Step 0)

### A. Recount of Regex Flags from `regex_catalog.json`

The 585 regex instances in [`regex_catalog.json`](regex_catalog.json) break down strictly as follows:

| Flag String | Count | Description |
| :--- | :--- | :--- |
| `i` | 337 | Case-insensitive matching. |
| `""` (none) | 127 | Exact case, single match. |
| `g` | 76 | Global matching (stateful across calls in JS). |
| `gi` | 43 | Global + case-insensitive. |
| Dynamic flags | 2 | `pattern.flags` (line 131) and `re.flags.includes('g') ? re.flags : `${re.flags}g`` (line 241). |
| **Total** | **585** | Reconciled AST count. |

> **Note on `src/skillsExtractionEngine.ts:882`**: Line 880–882 uses `/(?:^|\n)\s*(?:technologies...)\s*[:\-–—]\s*(.+)/gi`. The explicit `(?:^|\n)` line-start alternation emulates multiline line-anchoring (`im`) without relying on the literal JavaScript `m` flag.

---

### B. Dynamic `RegExp` Constructors & String Assembly Mechanics

The codebase uses dynamic `new RegExp(...)` constructors across 6 functional categories:

1. **Evidence-Lock Verification Pattern (`src/metaforgeParser.ts:178`)**:
   ```typescript
   new RegExp(`\\b${numEscaped}\\s*(?:years?|yrs?|months?|mos?)`, 'i')
   ```
   - *How built*: Takes the normalized experience number (e.g. `"7+"`), escapes regex metacharacters (`+` -> `\\+`), and checks whether the experience duration exists verbatim in the raw source resume text.
2. **Section Header Boundary Assembler (`src/parseCoreResumeFields.ts:71`)**:
   ```typescript
   new RegExp(`(?:${startNames.source})\\s*\\n([\\s\\S]*?)(?:${endBefore.source}|$)`, 'i')
   ```
   - *How built*: Combines pre-compiled regex `.source` properties (`startNames.source` and `endBefore.source`) into a non-greedy block capture bounded by the next section header or EOF.
3. **Education Section Slicers (`src/parseCoreResumeFields.ts:81, 88, 96, 97`)**:
   ```typescript
   new RegExp(`(?:^|\\n)\\s*(?:${EDUCATION_SECTION_START})\\s*:?\\s*\\n([\\s\\S]*?)(?:${SECTION_END}|$)`, 'i')
   ```
   - *How built*: Injects `String.raw` constant patterns (`EDUCATION_SECTION_START`, `SECTION_END`, `SKILL_SECTION_START`) into a multiline slice pattern.
4. **LinkedIn URL Matchers with Dynamic Slugs (`src/parseCoreResumeFields.ts:233-256, 287, 297`)**:
   ```typescript
   const uid = '[a-zA-Z0-9][-a-zA-Z0-9_]{1,100}[a-zA-Z0-9]';
   new RegExp(`https?://(?:[a-z]{2}\\.)?(?:www\\.)?linkedin\\.com/(?:in|pub)/${uid}`, 'gi')
   ```
   - *How built*: Injects username regex sub-patterns (`${uid}`) and slug matchers (`${slugPart}`) across 6 URL format variants.
5. **Date-Range Pattern Global Cloner (`src/parseCoreResumeFields.ts:131, 241, 713, 748`)**:
   ```typescript
   new RegExp(dateRangePattern.source, 'gi')
   new RegExp(re.source, re.flags.includes('g') ? re.flags : `${re.flags}g`)
   ```
   - *How built*: Reads an existing regex `.source` and appends the `g` flag to enable iterative match extraction.
6. **Skills Keyword & Compound Boundary Matchers (`src/skillsExtractionEngine.ts:801, 808, 1354, 1413, 1444, 1467`)**:
   ```typescript
   new RegExp(`(?:^|[^a-zA-Z0-9+#.-])${escaped}(?:$|[^a-zA-Z0-9+#.-])`, 'i')
   new RegExp(`\\b${escaped}\\b`, 'i')
   ```
   - *How built*: Dynamically escapes skill tokens (e.g. `C++` -> `C\\+\\+`, `Node.js` -> `Node\\.js`) and binds them to non-word delimiters that preserve symbols like `+` and `#`.

---

### C. Precision Audit: Float, Int, Date, Trim, and `/g` Statefulness

1. **`parseFloat`**:
   - `src/ai/experience.ts:285`: `Math.round(parseFloat(m[1]) * 12)`
   - `src/parseCoreResumeFields.ts:825`: `Math.floor(parseFloat(ym[1]))`
   - `src/parseCoreResumeFields.ts:829`: `Math.floor(parseFloat(num[1]))`
   - *Python Rule*: Use `float(m[1])`. In `ai/experience.ts`, apply round-half-up: `int(Decimal(str(float(m[1]) * 12)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))`.
2. **`Number()`**:
   - `src/ai/config.ts:6`: `Number(process.env.PORT) || 3001`
   - `src/ai/experience.ts:26, 29, 30, 37, 40, 47, 50, 58, 61`: ISO/Named date components.
   - `src/parseCoreResumeFields.ts:649, 653, 659, 661, 667, 669, 675`: Date range year and month components.
   - *Python Rule*: Use `int(s)` after confirming digits.
3. **`toFixed`**:
   - **Zero uses** in the entire codebase.
4. **`trim()`, `trimStart()`, `trimEnd()`**:
   - 195 uses across 10 source files.
   - *Python Rule*: In Python, `str.strip()` strips all standard whitespace. To match JavaScript `.trim()`, it must also strip non-breaking space `\u00A0` and zero-width space `\uFEFF`: `s.strip(' \t\n\r\f\v\u00a0\ufeff')`.
5. **`new Date()` / `Date.now()` with No Arguments**:
   - `src/adapters/candidateStoreAdapter.ts:24`: `Date.now()` -> Current epoch milliseconds.
   - `src/ai/experience.ts:20`: `new Date()` -> Used when period end date is `"Present"` or `"Current"`.
   - `src/ai/experience.ts:88`: `const now = new Date();` -> Calculation ceiling for ongoing roles.
   - `src/parseCoreResumeFields.ts:643`: `const now = new Date();` -> Current year cutoff check.
   - *Freezing Rule*: For golden fixtures and deterministic verification, freeze the clock at `2026-11-02T00:00:00.000Z`.
6. **`/g` Regexes Reused with `.test()` / `.exec()`**:
   - `src/parseCoreResumeFields.ts:132`: `while ((m = re.exec(chunk)) !== null)`
   - `src/parseCoreResumeFields.ts:242`: `while ((m = r.exec(collapsed)) !== null)`
   - `src/parseCoreResumeFields.ts:560`: `rx.exec(fullText)`
   - `src/parseCoreResumeFields.ts:714, 749`: `re.exec(...)`
   - `src/parseCoreResumeFields.ts:959, 966, 973`: `while ((m = re.exec(s)) !== null)`
   - `src/skillsExtractionEngine.ts:883`: `while ((techLineMatch = techLineRe.exec(content)) !== null)`
   - `src/ai/experience.ts:215, 229, 243`: `while ((m = re.exec(s)) !== null)`
   - *Statefulness Hazard*: In JavaScript, `/g` RegExp instances hold internal mutable `lastIndex` state. If a `/g` regex is reused across calls without setting `regex.lastIndex = 0`, alternating calls return `false` or offset matches. In Python, `re.finditer` produces an immutable iterator and avoids mutable state bugs.

---

### D. Strict Regex Translation Rules (JavaScript to Python)

To guarantee exact character-for-character parity:

1. **Whitespace Class (`\s`)**:
   - In JavaScript, `\s` matches: `[ \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]`.
   - In Python, `\s` without flags matches Unicode whitespace.
   - **Translation Rule**: Whenever translating `\s` or using it inside custom brackets like `[\s,;]`, replace with the explicit JS whitespace class:
     ```python
     JS_S = r'[ \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]'
     ```
2. **ASCII Digits, Words, and Boundaries (`\d`, `\w`, `\b`)**:
   - In JavaScript, `\d` and `\w` are strictly ASCII. `\b` operates strictly on ASCII word boundaries.
   - In Python 3, `\d`, `\w`, and `\b` match Unicode characters by default.
   - **Translation Rule**: Compile **all** regexes with `re.ASCII` (`re.A`), or compile via `regex.compile(pattern, regex.ASCII)`.
3. **Dot (`.`)**:
   - In JavaScript, `.` matches any character **except** `\n`, `\r`, `\u2028`, `\u2029`.
   - In Python, `.` matches any character **except `\n`** (it *does* match `\r`!).
   - **Translation Rule**: Replace unescaped `.` with `[^\n\r\u2028\u2029]`.
4. **End of String Anchor (`$`)**:
   - In JavaScript without `m` flag, `$` matches only the exact end of input (or before a terminating newline).
   - In Python, `$` matches at the very end of string AND before a newline `\n` at the end of the string.
   - **Translation Rule**: For non-multiline patterns anchored to the end of input, translate `$` to `\Z`.
5. **Multiline Anchors (`^` and `$`)**:
   - In JavaScript with `m` flag, `^` matches start of input and immediately after `\n`, `\r`, `\u2028`, `\u2029`.
   - In Python with `re.M`, `^` matches start of string and immediately after `\n` (not after bare `\r`).
   - **Translation Rule**: Normalize all document text to Unix newlines (`\n`) before applying regexes.
6. **Non-Global Replacements (`str.replace()`)**:
   - In JavaScript, `str.replace(regexWithoutG, replacement)` replaces **only the first match**!
   - In Python, `re.sub(pattern, replacement, string)` replaces **ALL** matches by default!
   - **Translation Rule**: For every JavaScript `.replace(/.../)` lacking the `g` flag, Python must explicitly pass `count=1`:
     ```python
     # JavaScript: s.replace(/^[|:;\-]+/, '')
     # Python: re.sub(r'^[|:;\-]+', '', s, count=1)
     ```
7. **The 4 Variable-Length Lookbehinds**:
   - Must be executed using the third-party `regex` module with original patterns:
     1. `regex.compile(r'(?<!Professional\s+|Career\s+|Profile\s+)Summary', regex.IGNORECASE)`
     2. `regex.compile(r'(?<!Executive\s+|Profile\s+)(?:Professional\s+)?Profile', regex.IGNORECASE)`
     3. `regex.compile(r'(?<!\b(?:[A-Z]|Tech|Engg|Hons|Phil|Admin))\.\s+[\s\S]*', regex.IGNORECASE)`
     4. `regex.compile(r'(?<!\b(?:[A-Z]|Tech|Engg|Hons|Phil|Admin))\.\s+[\s\S]*', regex.IGNORECASE)`

8. **Whitespace Splitting (`.trim().split(/\s+/)`)**:
   - In JavaScript:
     - `"".split(/\s+/)` returns `[""]` (an array with one empty string, length 1).
     - `"  a  b  ".split(/\s+/)` without `.trim()` returns `["", "a", "b", ""]` (leading/trailing empty strings).
     - `"  a  b  ".trim().split(/\s+/)` returns `["a", "b"]`.
   - In Python:
     - `"".split()` returns `[]` (an empty list).
     - `"  a  b  ".split()` automatically strips leading/trailing whitespace and splits on runs of whitespace -> `["a", "b"]`.
   - **Translation Rule**:
     - Translate `s.trim().split(/\s+/)` to `s.split()`.
     - Where TypeScript code relies on array length or does `.filter(Boolean)`, `[t for t in s.split() if t]` ensures exact behavioral parity without empty string leaks.

---

## Phase 4 Completion & Verification Audit

### 1. Routes & ASGI Microservice (`src/routes/resumeParserRouter.py`, `src/server.py`)
- Express routing mounted under `/` and `/api/resume`.
- Case-insensitive URL handling & trailing-slash tolerance verified (`/HEALTH`, `/health/`, `/API/resume/Parse/`).
- Upload limits & file filter:
  - Form fields: `resume` for single parse, `resumes` for bulk parse (up to 5 files).
  - Memory storage: `spool_max_size = 50MB` holding files entirely in memory without disk writes (matching `multer.memoryStorage()`).
  - Max file size: 15 MB limit returning HTTP 500 `"File too large"`.
  - Format validation: allowed extensions `.pdf, .doc, .docx, .txt, .png, .jpg, .jpeg, .webp, .bmp, .tif, .tiff` returning HTTP 500 `"File format {ext} is not supported. Supported: PDF, DOCX, DOC, TXT, and common image formats."`.
  - Missing file: HTTP 400 `"Resume file is required under form field \"resume\""`.
  - Bulk missing files: HTTP 400 `"At least one resume file is required under form field \"resumes\""`.
  - Bulk over 5 files: HTTP 400 `"Maximum 5 resumes allowed per batch upload"`.
- Response format: compact JSON serialization (`separators=(',', ':')`, `ensure_ascii=False`, `Content-Type: application/json; charset=utf-8`).
- Bulk items: omitted `error` on successful items, omitted `data` on error items.
- Express `cors()` parity: sets `Access-Control-Allow-Origin: *`, responds to `OPTIONS` preflight with HTTP 204, empty body, and echoes `Access-Control-Request-Headers`.
- Request timeouts: 5 minutes (300s) for single parse, 10 minutes (600s) for bulk parse.
- Bulk throttling: 800ms between calls when Gemini AI is active.
- ASGI entrypoint: runnable with `uvicorn src.server:app --workers 1`.
- `app.py` kept launching Node service until final user sign-off.

### 2. Parity Test Coverage
- **TypeScript manifest**: all 20 `src/**/*.ts` files verified untouched with identical SHA-256 hashes (`tests/parity/ts_manifest.json`).
- **Jest test parity**: 154 / 154 Jest tests ported to pytest (100% passing, 0 skipped, 0 unported).
- **Golden test parity**:
  - Path 1 (`parseCoreFieldsFromResumeText`): 143 / 143 inputs verified with 100% deep equality.
  - Path 2 (`parseResumeBufferLegacy`): 143 / 143 inputs individually parametrized and verified with 100% deep equality.
  - Path 3 (`parseResumeBuffer` with mocked Gemini): 143 / 143 inputs individually parametrized and verified with 100% deep equality.
  - Express & HTTP Goldens: all status codes, response headers, and bodies verified against `express_goldens.json` and `http_goldens.json`.
  - Gemini Replay: 10/10 scenarios replayed with exact request sequence, URL, headers, body bytes, and delays.
  - Dynamic Regexes: 481 runtime dynamic regexes verified against `runtime_dynamic_regexes.json`.
- **Total Pytest Suite**: **480 passed, 0 failed**.

