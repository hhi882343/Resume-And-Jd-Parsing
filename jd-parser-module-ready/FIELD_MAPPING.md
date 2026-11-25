# JD Parser Module – 28-Field ATS Schema & Mapping Guide

Every analyzed job requirement produces a validated Pydantic v2 `AnalyzedRequirement` object. When serialized to JSON (via `model_dump(by_alias=True)` or REST API response), fields use ECMAScript `camelCase` naming conventions.

---

## 1. Complete Field Catalog

| # | Python Field | JSON Alias | Type | Extraction Priority | Description & Business Rules | Example Value |
|---|:---|:---|:---|:---|:---|:---|
| 1 | `requirement_id` | `requirementId` | `string` | Auto-Generated | Unique tracking ID formatted as `REQ-YYYY-MM-DD-SEQ`. | `"REQ-2026-10-30-582"` |
| 2 | `role_index` | `roleIndex` | `integer` | Chunker Index | 1-based index of the position within the email/document. | `1` |
| 3 | `total_roles` | `totalRoles` | `integer` | Chunker Index | Total number of discrete job positions identified in the input. | `2` |
| 4 | `extraction_source` | `extractionSource` | `string` | Pipeline Audit | AI provider or engine used (`"gemini"`, `"sambanova"`, `"groq"`, etc.). | `"gemini"` |
| 5 | `correction_applied`| `correctionApplied`| `boolean` | Feedback Store | Indicates if a human correction overlay was merged. | `false` |
| 6 | `job_title` | `jobTitle` | `string` | Regex > LLM > Infer | Standardized job title. Generic titles (e.g. "Engineer") are inferred from skills. | `"Senior React Developer"` |
| 7 | `is_inferred_title`| `isInferredTitle` | `boolean` | Title Heuristics | `true` if title was algorithmically inferred rather than explicitly stated. | `false` |
| 8 | `client_lead_poc_from` | `clientLeadPocFrom` | `string` | Email Engine > LLM | Sender's display name and email extracted from email headers. | `"John Smith <john@corp.com>"` |
| 9 | `client_poc_from_cc` | `clientPocFromCc` | `string` | Email Engine > LLM | CC recipients extracted from email headers. Semicolon/comma separated. | `"Lead <lead@corp.com>"` |
| 10| `internal_poc_to` | `internalPocTo` | `string` | Email Engine > LLM | Direct recipient(s) of the email demand. | `"Recruiting <hr@agency.com>"` |
| 11| `requirement_from` | `requirementFrom` | `string` | Domain Parsing > LLM | Client company name parsed from email domain or text. | `"TechCorp Solutions"` |
| 12| `demand_received_date` | `demandReceivedDate` | `string` | Email Date > Clock | Date demand was received (`YYYY-MM-DD`). | `"2026-10-30"` |
| 13| `closed_date` | `closedDate` | `string` | Default | Target or actual requirement closing date. | `"Not specified"` |
| 14| `open_since` | `openSince` | `string` | Clock Calc | Relative age string (e.g., `"Today"`, `"3 days ago"`). | `"Today"` |
| 15| `type_of_demand` | `typeOfDemand` | `string` | Chunker Count | Categorized as `"Single"` (1 position) or `"Multiple"` (>1 positions). | `"Single"` |
| 16| `job_status` | `jobStatus` | `string` | Workflow | Current pipeline status. Defaults to `"Unassigned"`. | `"Unassigned"` |
| 17| `priority` | `priority` | `string` | Regex > LLM | Demand urgency: `"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`. | `"HIGH"` |
| 18| `relevant_experience` | `relevantExperience` | `string` | Regex > LLM | Hands-on experience in primary technology stack. | `"3-5 years"` |
| 19| `overall_experience` | `overallExperience` | `string` | Regex > LLM | Total industry experience required. | `"5-8 years"` |
| 20| `qualification_criteria`| `qualificationCriteria`| `string` | LLM > Regex | Educational degrees or certifications required. | `"B.Tech / MCA or equivalent"` |
| 21| `employment_type` | `employmentType` | `string` | Regex > LLM | `"Full Time"`, `"Contract"`, `"C2H"`, `"Part Time"`. | `"Full Time"` |
| 22| `work_mode` | `workMode` | `string` | Regex > LLM | `"On-site"`, `"Hybrid"`, `"Remote"`. | `"Hybrid"` |
| 23| `work_timings` | `workTimings` | `string` | Regex > LLM | Shift timings or working hours. | `"US Shift (6 PM - 3 AM IST)"` |
| 24| `location` | `location` | `string` | Regex > LLM | Job location or base city. | `"Bangalore"` |
| 25| `number_of_positions` | `numberOfPositions` | `string` | Regex > LLM | Number of headcount vacancies requested. | `"2"` |
| 26| `budget_currency` | `budgetCurrency` | `string` | Currency Normalizer | Currency symbol or ISO code: `"INR"`, `"USD"`, `"EUR"`, `"GBP"`. | `"INR"` |
| 27| `monthly_budget` | `monthlyBudget` | `string` | Budget Engine | Monthly compensation figure, preserving raw rate structure. | `"70,000 / month"` |
| 28| `annual_budget` | `annualBudget` | `string` | Budget Engine | Annual salary budget, preserving original expressions. | `"22-26 LPA"` |
| 29| `notice_period` | `noticePeriod` | `string` | Regex > LLM | Candidate availability timeframe. | `"Immediate to 15 days"` |
| 30| `sla` | `sla` | `string` | LLM > Default | Service Level Agreement turnaround target. | `"48 hours"` |
| 31| `mandatory_skills` | `mandatorySkills` | `List[string]` | Skill Canonicalizer | List of normalized core technical competencies. | `["Python", "FastAPI", "SQL"]` |
| 32| `technical_skills` | `technicalSkills` | `List[Object]` | LLM Rating Engine | Structured array of `{ "name": str, "rating": "1"-"5" }`. | `[{"name": "Python", "rating": "5"}]` |
| 33| `job_description` | `jobDescription` | `string` | Body Sanitizer | Cleaned text description with email disclaimers removed. | `"We are seeking an experienced..."` |
| 34| `email_headers` | `emailHeaders` | `Object` | Universal Engine | Raw parsed header contacts: `{"from": [...], "to": [...], "cc": [...]}`. | `{"from": [{"name": "...", "email": "..."}]}` |

---

## 2. Technical Skills Rating System

The `technicalSkills` array classifies required competencies with proficiency ratings from 1 to 5:

- **Rating 5 (Expert / Lead)**: Core mandatory skill explicitly emphasized as the primary requirement (e.g., "Must have deep expertise in Python").
- **Rating 4 (Advanced)**: Essential secondary or framework requirement (e.g., "Extensive experience with FastAPI and PostgreSQL").
- **Rating 3 (Intermediate / Working Knowledge)**: Complementary tools and libraries (e.g., "Working knowledge of Docker and Redis").
- **Rating 2 (Basic / Familiarity)**: Good to have or secondary skills mentioned in passing (e.g., "Familiarity with Kubernetes").
- **Rating 1 (Awareness)**: Optional or peripheral tools.

---

## 3. Missing Field Standard (`NOT_SPECIFIED`)

Whenever a field cannot be deterministically inferred from the input text, it is populated with the constant value:

```python
NOT_SPECIFIED = "Not specified"
```

This prevents `null`, `undefined`, or random empty strings from breaking downstream ATS databases and table rendering.

