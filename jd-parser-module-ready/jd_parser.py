"""JD Parser Module - Standalone Entry Point & Python SDK

Provides a direct programmatic interface for extracting structured ATS fields,
technical skills, budgets, and email headers from job descriptions and emails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.core.email_extractor import (
    EmailContact,
    ExtractedEmailHeaders,
    extract_universal_email_headers,
)
from app.schemas.requirement import AnalyzedRequirement, RequirementData
from app.services.extraction import orchestrate_analysis
from app.services.llm_client import BaseLLMClient, CascadeLLMClient


async def parse_jd(
    text: str,
    client: Optional[BaseLLMClient] = None,
    *,
    timezone: Optional[str] = None,
) -> List[AnalyzedRequirement]:
    """Parse raw job description text asynchronously into structured ATS requirements.

    Args:
        text: Raw job description or email text.
        client: Optional custom LLM client instance (defaults to CascadeLLMClient).
        timezone: Optional IANA timezone string (defaults to APP_TIMEZONE or UTC).

    Returns:
        List of AnalyzedRequirement objects containing the 28 ATS fields and metadata.
    """
    if not text or not text.strip():
        return []
    return await orchestrate_analysis(
        raw_text=text.strip(),
        session=None,
        client=client,
        timezone=timezone,
    )


def parse_jd_sync(
    text: str,
    client: Optional[BaseLLMClient] = None,
    *,
    timezone: Optional[str] = None,
) -> List[AnalyzedRequirement]:
    """Synchronous wrapper for parse_jd for use in sync frameworks (Django, Flask, Celery, scripts).

    Args:
        text: Raw job description or email text.
        client: Optional custom LLM client instance.
        timezone: Optional IANA timezone string.

    Returns:
        List of AnalyzedRequirement objects.
    """
    return asyncio.run(parse_jd(text, client=client, timezone=timezone))


def parse_email_headers(text: str) -> Dict[str, Any]:
    """Extract sender, recipient, CC contacts, and subject from email text without LLM invocation.

    Returns:
        Dictionary conforming to the universal email headers schema:
        {
            "has_headers": bool,
            "subject": str,
            "date": str,
            "from": [{"name": str, "email": str}],
            "to": [{"name": str, "email": str}],
            "cc": [{"name": str, "email": str}]
        }
    """
    res: ExtractedEmailHeaders = extract_universal_email_headers(text)
    return {
        "has_headers": res.has_headers,
        "subject": res.subject or "",
        "date": res.date or "",
        "from": [{"name": c.name, "email": c.email} for c in res.from_contacts],
        "to": [{"name": c.name, "email": c.email} for c in res.to_contacts],
        "cc": [{"name": c.name, "email": c.email} for c in res.cc_contacts],
    }


def main() -> None:
    """CLI runner for parsing a JD file or text input."""
    parser = argparse.ArgumentParser(description="JD Parser Standalone CLI")
    parser.add_argument("file_or_text", help="Path to text/email file or literal raw text to parse")
    parser.add_argument(
        "--headers-only",
        action="store_true",
        help="Extract email headers only without running LLM extraction",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation level for stdout (default: 2)",
    )

    args = parser.parse_args()

    # Determine if input is a file path or literal text
    target_path = Path(args.file_or_text)
    if target_path.exists() and target_path.is_file():
        text_content = target_path.read_text(encoding="utf-8")
    else:
        text_content = args.file_or_text

    if args.headers_only:
        headers = parse_email_headers(text_content)
        print(json.dumps(headers, indent=args.indent, ensure_ascii=False))
        return

    results = parse_jd_sync(text_content)
    output = [r.model_dump(by_alias=True) for r in results]
    print(json.dumps(output, indent=args.indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
