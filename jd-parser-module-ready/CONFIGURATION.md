# JD Parser Module – Configuration & Provider Reference

## 1. Environment Variables Reference

All configuration is managed through standard environment variables or a `.env` file in the working root, loaded automatically via `pydantic-settings`.

| Variable | Type | Default | Required? | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | `string` | `None` | **Recommended** | Primary LLM API key for Google Gemini. |
| `GEMINI_MODEL` | `string` | `gemini-2.5-flash-lite` | No | Model name for Google Gemini. |
| `SAMBANOVA_API_KEY` | `string` | `None` | Optional | First fallback LLM provider API key (SambaNova Cloud). |
| `SAMBANOVA_MODEL` | `string` | `Meta-Llama-3.3-70B-Instruct` | No | Model name for SambaNova. |
| `GROQ_API_KEY` | `string` | `None` | Optional | Second fallback LLM provider API key (Groq Cloud). |
| `GROQ_MODEL` | `string` | `llama-3.3-70b-versatile` | No | Model name for Groq. |
| `OPENROUTER_API_KEY` | `string` | `None` | Optional | Third fallback LLM provider API key (OpenRouter). |
| `OPENROUTER_MODEL` | `string` | `meta-llama/llama-3.3-70b-instruct:free` | No | Model name for OpenRouter. |
| `DATABASE_URL` | `string` | `sqlite+aiosqlite:///data/feedback.db` | No | Database connection URL. Only accessed when `session` is passed. |
| `APP_TIMEZONE` | `string` | `None` (System Local) | No | IANA timezone name (e.g. `'UTC'`, `'Asia/Kolkata'`). |
| `API_KEY_AUTH_ENABLED` | `boolean` | `false` | No | When `true`, enforces `X-API-Key` header on REST routes. |
| `APP_API_KEY` | `string` | `None` | Conditional | Secret key required when `API_KEY_AUTH_ENABLED=true`. |
| `CORS_ORIGINS` | `string` | `""` | No | Comma-separated list of allowed origins (e.g., `*` or `http://localhost:3000`). |
| `ENABLE_DOCS` | `boolean` | `true` | No | Enables OpenAPI docs (`/docs` and `/redoc`). |
| `APP_HOST` | `string` | `0.0.0.0` | No | Bind host for FastAPI server. |
| `APP_PORT` | `integer` | `8000` | No | Bind port for FastAPI server. |

---

## 2. AI Provider Cascade & Failover Order

The parser employs a 4-tier provider cascade. If a provider encounters rate limits (HTTP 429), server downtime (HTTP 503), or quota exhaustion, it immediately transfers execution to the next provider:

```text
[Tier 1: Google Gemini]
        │ (on 429 / 503 / quota error)
        ▼
[Tier 2: SambaNova Systems (Llama 3.3 70B)]
        │ (on 429 / 503 / quota error)
        ▼
[Tier 3: Groq Cloud (Llama 3.3 70B)]
        │ (on 429 / 503 / quota error)
        ▼
[Tier 4: OpenRouter (Llama 3.3 70B Free/Paid)]
```

### Provider Setup Guides:

1. **Google Gemini (Primary)**:
   - Portal: [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Pricing: High free tier allowance; sub-cent costs per 1,000 JDs.
   - Recommended: `gemini-2.5-flash-lite` (native JSON mode, lowest latency).

2. **SambaNova Systems (Fallback 1)**:
   - Portal: [SambaNova Cloud](https://cloud.sambanova.ai/)
   - Provides ultra-fast Llama 3.3 70B inference with full JSON schema compliance.

3. **Groq Cloud (Fallback 2)**:
   - Portal: [Groq Console](https://console.groq.com/)
   - Exceptional inference speed via LPUs.

4. **OpenRouter (Fallback 3)**:
   - Portal: [OpenRouter](https://openrouter.ai/)
   - Broad model access with both free and pay-as-you-go tiers.

---

## 3. Timezone Configuration

Date parsing and standard `demandReceivedDate` resolution use the application clock abstraction.
To lock the engine to a specific timezone regardless of the host server location, set:

```ini
APP_TIMEZONE=Asia/Kolkata
# or
APP_TIMEZONE=UTC
```

When unset, the parser automatically adapts to the host operating system's local timezone.

---

## 4. API Key Security & Authentication

If deploying the REST microservice to an untrusted or internal network, enable API key authentication:

```ini
API_KEY_AUTH_ENABLED=true
APP_API_KEY=production_secret_token_abc123xyz
```

Incoming HTTP requests must include the header:
```http
X-API-Key: production_secret_token_abc123xyz
```
Unauthorized requests will receive HTTP 401 Unauthorized.

