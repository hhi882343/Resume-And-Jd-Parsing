"""Injectable system clock for deterministic timestamps and relative date calculations.

Production code uses the real current time by default.
Pinned instants may only be configured by tests or test fixtures.
"""

from __future__ import annotations

import zoneinfo
from datetime import datetime, timezone, tzinfo
from typing import Callable, Optional

from app.config import settings


def _real_now() -> datetime:
    return datetime.now(timezone.utc)


_current_clock: Callable[[], datetime] = _real_now
_override_timezone: Optional[tzinfo] = None


def now() -> datetime:
    """Return the current datetime (UTC), defaulting to real system time."""
    return _current_clock()


def get_app_timezone() -> tzinfo:
    """Return the configured application timezone, defaulting to the system local timezone."""
    if _override_timezone is not None:
        return _override_timezone
    tz_name = settings.APP_TIMEZONE
    if tz_name:
        try:
            return zoneinfo.ZoneInfo(tz_name)
        except Exception:
            pass
    # System local timezone fallback (matching Node.js process.env.TZ / system default)
    return datetime.now().astimezone().tzinfo or timezone.utc


def set_app_timezone(tz: Optional[str | tzinfo]) -> None:
    """Explicitly override the application timezone for tests."""
    global _override_timezone
    if tz is None:
        _override_timezone = None
    elif isinstance(tz, str):
        _override_timezone = zoneinfo.ZoneInfo(tz)
    else:
        _override_timezone = tz


def reset_app_timezone() -> None:
    """Reset application timezone override to default configuration."""
    global _override_timezone
    _override_timezone = None


def local_now() -> datetime:
    """Return the current datetime converted to the application timezone."""
    return now().astimezone(get_app_timezone())


def set_clock(dt: Optional[datetime]) -> None:
    """Set the system clock to a fixed datetime (or reset to real time if None)."""
    global _current_clock
    if dt is None:
        _current_clock = _real_now
    else:
        fixed_dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        def _fixed_clock() -> datetime:
            return fixed_dt

        _current_clock = _fixed_clock


def reset_to_real_time() -> None:
    """Reset clock to real system time."""
    global _current_clock
    _current_clock = _real_now
