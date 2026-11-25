"""FastAPI application for JD Analyser platform.

Mounts endpoints at exact TypeScript paths:
- POST /api/analyze
- POST /api/corrections
- GET  /api/feedback/stats

Provides:
- Lifespan context for async engine disposal
- Exact ECMAScript JSON response formatting via JSJSONResponse
- Optional API key authentication (API_KEY_AUTH_ENABLED, off by default)
- Optional CORS middleware (CORS_ORIGINS, off by default)
- Optional OpenAPI documentation (ENABLE_DOCS, off by default)
"""

from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.response import JSJSONResponse
from app.api.v1.analyze import router as analyze_router
from app.api.v1.corrections import router as corrections_router
from app.api.v1.email import router as email_router
from app.api.v1.feedback import router as feedback_router
from app.config import settings
from app.db.session import async_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager managing database engine lifecycle."""
    yield
    await async_engine.dispose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings.API_KEY_AUTH_ENABLED and not (
        settings.APP_API_KEY and settings.APP_API_KEY.strip()
    ):
        raise RuntimeError(
            "APP_API_KEY must be configured with a non-empty key when API_KEY_AUTH_ENABLED is true"
        )

    docs_url = "/docs" if settings.ENABLE_DOCS else None
    redoc_url = "/redoc" if settings.ENABLE_DOCS else None
    openapi_url = "/openapi.json" if settings.ENABLE_DOCS else None

    application = FastAPI(
        title="JD Analyser API",
        description="Pure-Python backend API for JD extraction, human feedback, and DPO alignment.",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        default_response_class=JSJSONResponse,
        lifespan=lifespan,
    )

    # Optional CORS middleware (disabled when CORS_ORIGINS is empty)
    if settings.CORS_ORIGINS:
        origins = [orig.strip() for orig in settings.CORS_ORIGINS.split(",") if orig.strip()]
        if origins:
            application.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

    # Optional API key authentication middleware (disabled when API_KEY_AUTH_ENABLED is false)
    class APIKeyAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if settings.API_KEY_AUTH_ENABLED and request.url.path.startswith("/api/"):
                api_key = request.headers.get("X-API-Key") or ""
                expected_key = settings.APP_API_KEY or ""
                if not api_key or not secrets.compare_digest(api_key, expected_key):
                    return JSJSONResponse(
                        {"error": "Invalid or missing API key"},
                        status_code=401,
                    )
            return await call_next(request)

    application.add_middleware(APIKeyAuthMiddleware)

    # Standardized JSON error response for HTTP exceptions
    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSJSONResponse({"error": exc.detail}, status_code=exc.status_code)

    # Mount routers at exact TypeScript paths (no /v1 aliases)
    application.include_router(analyze_router)
    application.include_router(corrections_router)
    application.include_router(feedback_router)
    application.include_router(email_router)

    return application


app = create_app()
