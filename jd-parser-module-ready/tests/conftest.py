"""Pytest shared test fixtures and configuration."""

from __future__ import annotations

import os

# Ensure APP_TIMEZONE=UTC for all tests
os.environ["APP_TIMEZONE"] = "UTC"

from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import pytest

from app.config import Settings
from app.core import clock

TEST_FROZEN_INSTANT = datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def freeze_clock(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Pin the clock to 2026-10-30T12:00:00Z and APP_TIMEZONE=UTC for deterministic tests unless marked unpinned_clock."""
    clock.set_app_timezone("UTC")
    if "unpinned_clock" in request.keywords:
        clock.reset_to_real_time()
        try:
            yield
        finally:
            clock.reset_app_timezone()
        return

    clock.set_clock(TEST_FROZEN_INSTANT)
    try:
        yield
    finally:
        clock.reset_to_real_time()
        clock.reset_app_timezone()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Fixture returning application settings configured for test environment."""
    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        POLICY_VERSION="test-policy",
        API_KEY_AUTH_ENABLED=False,
        APP_TIMEZONE="UTC",
    )


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Returns path to tests/fixtures directory."""
    return Path(__file__).parent / "fixtures"
