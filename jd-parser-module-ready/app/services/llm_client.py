"""Asynchronous LLM client interface and multi-provider cascade implementation.

Ports exact model chain, generation config, retry, backoff, fallback cascade,
and error-handling from TypeScript src/lib/gemini-helpers.ts and src/lib/llm-extract.ts.
Security requirement: Never logs or prints API keys or full prompts containing JD text.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.services.prompts import (
    MISSING_KEY_MESSAGE,
    SPLIT_REQUIREMENTS_PROMPT,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# Node.js `fetch` has no default timeout (it defaults to system socket timeout / infinite).
# In contrast, Python httpx defaults to 5.0 seconds, which causes premature timeouts
# during LLM inference. We configure a generous 300.0s (5 minutes) timeout so Python
# does not time out earlier than Node fetch would.
DEFAULT_HTTP_TIMEOUT = httpx.Timeout(300.0)

DEFAULT_GEMINI_FALLBACKS: List[str] = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-2.5-pro",
]


def is_retryable_gemini_error(message: str) -> bool:
    """Check if an error message represents a retryable Gemini / LLM error.

    Ported verbatim from src/lib/gemini-helpers.ts lines 21-33.
    """
    msg_lower = message.lower()
    return (
        "429" in message
        or "503" in message
        or "rate limit" in msg_lower
        or "high demand" in msg_lower
        or "quota exceeded" in msg_lower
        or "rate_limit_exceeded" in message
        or "overloaded" in msg_lower
        or "unavailable" in msg_lower
        or "temporarily unavailable" in msg_lower
    )


def is_valid_key(key: Optional[str], placeholder: str) -> bool:
    """Check whether an API key is valid and not a placeholder.

    Ported verbatim from src/lib/llm-extract.ts lines 298-301.
    """
    if not key or not key.strip():
        return False
    return placeholder not in key and len(key.strip()) > 10


def get_configured_provider(settings_obj=None) -> Optional[str]:
    """Determine primary LLM provider based on configured API keys.

    Ported verbatim from src/lib/llm-extract.ts lines 303-327.
    """
    cfg = settings_obj or settings
    if cfg.GEMINI_API_KEY and cfg.GEMINI_API_KEY.strip():
        return "gemini"
    if cfg.SAMBANOVA_API_KEY and cfg.SAMBANOVA_API_KEY.strip():
        return "sambanova"
    if is_valid_key(cfg.GROQ_API_KEY, "your-groq"):
        return "groq"
    if is_valid_key(cfg.OPENROUTER_API_KEY, "your-openrouter"):
        return "openrouter"
    return None


class BaseLLMClient(ABC):
    """Abstract interface for recruitment extraction LLM clients."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier string (e.g. 'gemini', 'synthetic-baseline')."""
        ...

    @abstractmethod
    async def extract(
        self,
        prompt: str,
        *,
        raw_text: Optional[str] = None,
        sample_id: Optional[str] = None,
        json_mode: bool = True,
        retries_per_model: int = 3,
    ) -> str:
        """Execute extraction call against LLM and return raw response string."""
        ...


class GeminiClient(BaseLLMClient):
    """Google Gemini LLM client implementing the exact TS fallback chain and backoff."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[httpx.Timeout] = None,
    ) -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._configured_model = model or settings.GEMINI_MODEL
        self._timeout = timeout or DEFAULT_HTTP_TIMEOUT

    @property
    def provider_name(self) -> str:
        return "gemini"

    def __repr__(self) -> str:
        # Redact key in representations
        return f"<GeminiClient model={self._configured_model!r}>"

    def get_model_chain(self) -> List[str]:
        """Return unique list of models to try in order matching src/lib/gemini-helpers.ts."""
        primary = (
            self._configured_model.strip() if self._configured_model else "gemini-2.5-flash-lite"
        )
        chain = [primary, *DEFAULT_GEMINI_FALLBACKS]
        seen = set()
        unique_chain = []
        for m in chain:
            if m not in seen:
                seen.add(m)
                unique_chain.append(m)
        return unique_chain

    async def extract(
        self,
        prompt: str,
        *,
        raw_text: Optional[str] = None,
        sample_id: Optional[str] = None,
        json_mode: bool = True,
        retries_per_model: int = 3,
    ) -> str:
        """Generate content with Gemini using model chain fallback and exponential backoff."""
        if not self._api_key or not self._api_key.strip():
            raise RuntimeError("No GEMINI_API_KEY configured")

        models = self.get_model_chain()
        last_error: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for model_name in models:
                for attempt in range(retries_per_model):
                    try:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                        headers = {
                            "Content-Type": "application/json",
                            "x-goog-api-key": self._api_key.strip(),
                        }
                        payload = {
                            "generationConfig": {
                                "temperature": 0,
                                **({"responseMimeType": "application/json"} if json_mode else {}),
                            },
                            "safetySettings": [],
                            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        }

                        response = await client.post(url, headers=headers, json=payload)

                        if response.status_code != 200:
                            err_body = (
                                response.json()
                                if response.headers.get("content-type", "").startswith(
                                    "application/json"
                                )
                                else {}
                            )
                            err_msg = (
                                err_body.get("error", {}).get("message")
                                or f"HTTP {response.status_code}: {response.text}"
                            )
                            raise RuntimeError(f"[{response.status_code}] {err_msg}")

                        data = response.json()
                        candidates = data.get("candidates") or []
                        if not candidates:
                            raise RuntimeError("Empty response from Gemini")

                        first_cand = candidates[0]
                        if first_cand.get("finishReason") == "SAFETY":
                            raise RuntimeError(
                                "[GoogleGenerativeAI Error]: Candidate was blocked due to SAFETY"
                            )

                        parts = first_cand.get("content", {}).get("parts") or []
                        if not parts or not parts[0].get("text"):
                            raise RuntimeError("Empty response from Gemini")

                        content = parts[0]["text"]
                        if model_name != models[0]:
                            logger.info(f"Gemini succeeded with fallback model: {model_name}")

                        return content

                    except Exception as exc:
                        message = str(exc)
                        last_error = exc

                        if is_retryable_gemini_error(message) and attempt < retries_per_model - 1:
                            backoff = (2**attempt) * 1.5
                            logger.warning(
                                f"Gemini {model_name} busy. Retrying in {backoff}s ({attempt + 1}/{retries_per_model})..."
                            )
                            await asyncio.sleep(backoff)
                            continue

                        if is_retryable_gemini_error(message):
                            logger.warning(f"Gemini {model_name} unavailable. Trying next model...")
                            break

                        raise last_error

        raise last_error or RuntimeError("All Gemini models failed")

    async def infer_job_title(
        self, requirement_text: str, skills: Optional[List[str]] = None
    ) -> Optional[str]:
        """Infer professional job title matching src/lib/gemini-helpers.ts:117-136."""
        skills_list = skills or []
        from app.services.prompts import build_title_inference_prompt

        prompt = build_title_inference_prompt(requirement_text, skills_list)
        try:
            content = await self.extract(prompt, raw_text=requirement_text, json_mode=True)
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                title = str(parsed.get("jobTitle") or "").strip()
                return title or None
        except Exception as exc:
            logger.warning(f"Gemini title inference failed: {exc}")
        return None


class OpenAIChatCompatibleClient(BaseLLMClient):
    """Base client for OpenAI-compatible chat completion APIs (Groq, SambaNova, OpenRouter).

    Ported verbatim from src/lib/llm-extract.ts callChatApi (lines 396-443).
    """

    def __init__(
        self,
        endpoint_url: str,
        api_key: Optional[str],
        model: str,
        extra_headers: Optional[Dict[str, str]] = None,
        provider_id: str = "openai-compatible",
        timeout: Optional[httpx.Timeout] = None,
    ) -> None:
        self._endpoint_url = endpoint_url
        self._api_key = api_key
        self._model = model
        self._extra_headers = extra_headers or {}
        self._provider_id = provider_id
        self._timeout = timeout or DEFAULT_HTTP_TIMEOUT

    @property
    def provider_name(self) -> str:
        return self._provider_id

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} provider={self._provider_id!r} model={self._model!r}>"

    def _build_messages(self, prompt: str, raw_text: Optional[str] = None) -> List[Dict[str, str]]:
        """Format chat messages matching TypeScript system/user splitting."""
        if prompt.startswith(SYSTEM_PROMPT):
            user_part = prompt[len(SYSTEM_PROMPT) :].strip()
            return [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_part},
            ]
        if prompt.startswith(SPLIT_REQUIREMENTS_PROMPT):
            user_part = (
                raw_text
                if raw_text is not None
                else prompt[len(SPLIT_REQUIREMENTS_PROMPT) :].strip()
            )
            if user_part.startswith("Input:\n\n"):
                user_part = user_part[len("Input:\n\n") :].strip()
            elif user_part.startswith("Input:\n"):
                user_part = user_part[len("Input:\n") :].strip()
            return [
                {"role": "system", "content": SPLIT_REQUIREMENTS_PROMPT},
                {"role": "user", "content": user_part},
            ]
        # Generic fallback
        return [{"role": "user", "content": prompt}]

    async def extract(
        self,
        prompt: str,
        *,
        raw_text: Optional[str] = None,
        sample_id: Optional[str] = None,
        json_mode: bool = True,
        retries_per_model: int = 3,
    ) -> str:
        """Call chat completions API matching TypeScript callChatApi."""
        auth_header = f"Bearer {self._api_key}" if self._api_key is not None else "Bearer undefined"
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            **self._extra_headers,
        }

        payload: Dict[str, Any] = {
            "model": self._model,
            "temperature": 0,
            "messages": self._build_messages(prompt, raw_text),
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._endpoint_url, headers=headers, json=payload)

            if response.status_code != 200:
                try:
                    body = response.json()
                    msg = (
                        body.get("error", {}).get("message")
                        or f"LLM API error ({response.status_code})"
                    )
                except Exception:
                    msg = f"LLM API error ({response.status_code})"
                raise RuntimeError(msg)

            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError("Empty response from LLM")

            content = choices[0].get("message", {}).get("content")
            if not content:
                raise RuntimeError("Empty response from LLM")

            return content


class GroqClient(OpenAIChatCompatibleClient):
    """Groq Cloud LLM client ported from src/lib/llm-extract.ts lines 445-468."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[httpx.Timeout] = None,
    ) -> None:
        super().__init__(
            endpoint_url="https://api.groq.com/openai/v1/chat/completions",
            api_key=api_key or settings.GROQ_API_KEY,
            model=model or settings.GROQ_MODEL,
            provider_id="groq",
            timeout=timeout,
        )


class SambaNovaClient(OpenAIChatCompatibleClient):
    """SambaNova Systems LLM client ported from src/lib/llm-extract.ts lines 469-494."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[httpx.Timeout] = None,
    ) -> None:
        super().__init__(
            endpoint_url="https://api.sambanova.ai/v1/chat/completions",
            api_key=api_key or settings.SAMBANOVA_API_KEY,
            model=model or settings.SAMBANOVA_MODEL,
            provider_id="sambanova",
            timeout=timeout,
        )


class OpenRouterClient(OpenAIChatCompatibleClient):
    """OpenRouter LLM client ported from src/lib/llm-extract.ts lines 495-524."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[httpx.Timeout] = None,
    ) -> None:
        super().__init__(
            endpoint_url="https://openrouter.ai/api/v1/chat/completions",
            api_key=api_key or settings.OPENROUTER_API_KEY,
            model=model or settings.OPENROUTER_MODEL,
            extra_headers={
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "JD Analyser",
            },
            provider_id="openrouter",
            timeout=timeout,
        )


class CascadeLLMClient(BaseLLMClient):
    """Full multi-provider cascade client.

    Implements the exact provider cascade from src/lib/llm-extract.ts extractWithLlm (lines 566-630):
    1. Try primary configured provider (Gemini, SambaNova, Groq, OpenRouter).
    2. If primary is Gemini and it fails with a retryable/transient error:
       - Fallback 1: Groq (if GROQ_API_KEY configured)
       - Fallback 2: SambaNova (if SAMBANOVA_API_KEY configured)
       - Fallback 3: OpenRouter (if OPENROUTER_API_KEY configured)
       - If all fail: raise RuntimeError("All providers failed. Last error: {errorMessage}")
    3. If primary is not Gemini, or error is not retryable, re-raise original error.
    """

    def __init__(
        self,
        primary_provider: Optional[str] = None,
        gemini_client: Optional[BaseLLMClient] = None,
        groq_client: Optional[BaseLLMClient] = None,
        sambanova_client: Optional[BaseLLMClient] = None,
        openrouter_client: Optional[BaseLLMClient] = None,
    ) -> None:
        self._configured_primary = primary_provider
        self._gemini = gemini_client or GeminiClient()
        self._groq = groq_client or GroqClient()
        self._sambanova = sambanova_client or SambaNovaClient()
        self._openrouter = openrouter_client or OpenRouterClient()
        self._last_source: str = "gemini"

    @property
    def provider_name(self) -> str:
        return self._last_source

    def __repr__(self) -> str:
        return f"<CascadeLLMClient primary={self._configured_primary!r} last_source={self._last_source!r}>"

    async def infer_job_title(
        self, requirement_text: str, skills: Optional[List[str]] = None
    ) -> Optional[str]:
        """Infer professional job title matching src/lib/gemini-helpers.ts:117-136."""
        return await self._gemini.infer_job_title(requirement_text, skills)

    async def extract_with_provider(
        self,
        prompt: str,
        *,
        raw_text: Optional[str] = None,
        sample_id: Optional[str] = None,
        json_mode: bool = True,
        retries_per_model: int = 3,
    ) -> Tuple[str, str]:
        """Execute extraction call with provider cascade and return (content, provider_name)."""
        provider = self._configured_primary or get_configured_provider()
        if not provider:
            raise RuntimeError(MISSING_KEY_MESSAGE)

        # Primary dispatch
        primary_client = (
            self._gemini
            if provider == "gemini"
            else self._sambanova
            if provider == "sambanova"
            else self._groq
            if provider == "groq"
            else self._openrouter
        )

        try:
            content = await primary_client.extract(
                prompt,
                raw_text=raw_text,
                sample_id=sample_id,
                json_mode=json_mode,
                retries_per_model=retries_per_model,
            )
            self._last_source = provider
            return content, provider
        except Exception as exc:
            error_message = str(exc)
            is_transient = is_retryable_gemini_error(error_message)

            if is_transient and provider == "gemini":
                logger.error("Gemini unavailable. Trying fallback providers...")

                # 1. Try Groq
                if settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip():
                    try:
                        logger.info("Attempting fallback to Groq...")
                        content = await self._groq.extract(
                            prompt,
                            raw_text=raw_text,
                            sample_id=sample_id,
                            json_mode=json_mode,
                        )
                        self._last_source = "groq"
                        return content, "groq"
                    except Exception as groq_err:
                        logger.error(f"Groq fallback failed: {groq_err}")

                # 2. Try SambaNova
                if settings.SAMBANOVA_API_KEY and settings.SAMBANOVA_API_KEY.strip():
                    try:
                        logger.info("Attempting fallback to SambaNova...")
                        content = await self._sambanova.extract(
                            prompt,
                            raw_text=raw_text,
                            sample_id=sample_id,
                            json_mode=json_mode,
                        )
                        self._last_source = "sambanova"
                        return content, "sambanova"
                    except Exception as samba_err:
                        logger.error(f"SambaNova fallback failed: {samba_err}")

                # 3. Try OpenRouter
                if settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip():
                    try:
                        logger.info("Attempting fallback to OpenRouter...")
                        content = await self._openrouter.extract(
                            prompt,
                            raw_text=raw_text,
                            sample_id=sample_id,
                            json_mode=json_mode,
                        )
                        self._last_source = "openrouter"
                        return content, "openrouter"
                    except Exception as openrouter_err:
                        logger.error(f"OpenRouter fallback failed: {openrouter_err}")

                raise RuntimeError(f"All providers failed. Last error: {error_message}") from exc

            raise

    async def extract(
        self,
        prompt: str,
        *,
        raw_text: Optional[str] = None,
        sample_id: Optional[str] = None,
        json_mode: bool = True,
        retries_per_model: int = 3,
    ) -> str:
        """Execute extraction call with cascade and return content string."""
        content, _ = await self.extract_with_provider(
            prompt,
            raw_text=raw_text,
            sample_id=sample_id,
            json_mode=json_mode,
            retries_per_model=retries_per_model,
        )
        return content


# Alias matching TypeScript / documentation naming
ProviderCascadeClient = CascadeLLMClient
