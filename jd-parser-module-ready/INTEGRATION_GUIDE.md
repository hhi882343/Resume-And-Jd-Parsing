# JD Parser Module – Developer Integration Guide

This guide covers how to integrate the JD Parser Engine into existing systems, backend web frameworks (Django, Flask, FastAPI), background task queues (Celery), and containerized microservice architectures.

---

## 1. Integration Approaches at a Glance

| Approach | Best For | Latency | Language |
| :--- | :--- | :--- | :--- |
| **Direct Library Import** | Python backends (FastAPI, Django, Flask, Celery) | Lowest (in-process) | Python 3.10+ |
| **REST API Microservice** | Non-Python systems (Node.js, Go, Java, PHP, React) | Low (HTTP JSON) | Any |
| **CLI / Batch Process** | Data pipelines, cron jobs, terminal utilities | Low (process exec) | CLI / Shell |

---

## 2. Approach 1: Direct Python Library Integration

Copy the `app/` and `jd_parser.py` directory into your project, or install `jd-parser-module` into your virtualenv.

### A. FastAPI / Async Framework Integration

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from jd_parser import parse_jd
from app.schemas.requirement import AnalyzedRequirement

app = FastAPI(title="Recruitment Service")

class ParseRequest(BaseModel):
    raw_text: str

@app.post("/extract-requirements", response_model=List[AnalyzedRequirement])
async def extract_requirements(payload: ParseRequest):
    if not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="JD text is required")
    
    # Asynchronous parsing with automatic LLM cascade
    requirements = await parse_jd(payload.raw_text)
    return requirements
```

### B. Django Integration (Sync Views & Models)

```python
# views.py or services.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from jd_parser import parse_jd_sync, parse_email_headers

@csrf_exempt
def analyze_jd_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status_code=405)
    
    body = json.loads(request.body.decode("utf-8"))
    raw_text = body.get("text", "")
    
    # parse_jd_sync safely executes in synchronous Django worker threads
    results = parse_jd_sync(raw_text)
    
    # Convert Pydantic schemas to native Python dicts for Django JsonResponse
    data = [req.model_dump(by_alias=True) for req in results]
    return JsonResponse({"requirements": data}, safe=False)
```

### C. Celery Worker (Asynchronous Background Job)

```python
# tasks.py
from celery import shared_task
from jd_parser import parse_jd_sync

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_incoming_email_jd(self, email_raw_text: str):
    try:
        results = parse_jd_sync(email_raw_text)
        for req in results:
            # Save to your existing ATS database tables
            save_to_database(req)
        return len(results)
    except Exception as exc:
        raise self.retry(exc=exc)
```

---

## 3. Approach 2: REST API Microservice Integration

Run the parser as a dedicated HTTP microservice.

### Launching the Server:

```bash
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 4
```

### Calling from Node.js / TypeScript:

```typescript
import axios from 'axios';

interface ParseResponse {
  requirementId: string;
  jobTitle: string;
  overallExperience: string;
  monthlyBudget: string;
  annualBudget: string;
  skills: Array<{ name: string; rating: string }>;
  emailHeaders: {
    from: Array<{ name: string; email: string }>;
    to: Array<{ name: string; email: string }>;
    cc: Array<{ name: string; email: string }>;
  };
}

async function parseJobDescription(rawText: string): Promise<ParseResponse[]> {
  const response = await axios.post<ParseResponse[]>('http://localhost:8000/api/analyze', {
    rawJdText: rawText,
  });
  return response.data;
}
```

---

## 4. Docker Deployment

### Production `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY jd_parser.py .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  jd-parser:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_MODEL=gemini-2.5-flash-lite
      - SAMBANOVA_API_KEY=${SAMBANOVA_API_KEY}
      - GROQ_API_KEY=${GROQ_API_KEY}
    restart: always
```

---

## 5. Error Handling & Edge Cases

1. **Empty / Non-String Inputs**:
   - `parse_jd("")` returns an empty list `[]`.
   - The REST API `/api/analyze` returns HTTP 400 `{"error": "Job description text is required"}`.

2. **AI Rate Limiting (HTTP 429)**:
   - When all providers in the cascade fail or return quota exhaustion, the engine raises `AnalyzeRateLimitError`.
   - The REST API translates this to HTTP 429 with `{ "error": "High demand. Please wait a moment and try again." }`.

3. **Multiple Roles vs. Single Role**:
   - The returned result is always a `List[AnalyzedRequirement]`.
   - For a single JD, `len(results) == 1`, `roleIndex == 1`, `totalRoles == 1`.
   - For an email with multiple roles, `len(results) == N`, and each record has `roleIndex == i` with shared client header metadata.

