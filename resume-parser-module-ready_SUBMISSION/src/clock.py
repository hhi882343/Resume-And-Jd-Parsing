"""
Clock abstraction for deterministic testing and runtime date resolution.
Provides local time semantics matching JavaScript new Date().getFullYear() / getMonth().
Supports explicit timezone offsets (e.g. UTC +00:00 or IST +05:30).
"""
import datetime
from contextlib import contextmanager
from typing import Optional, Union

_FROZEN_DATE: Optional[datetime.datetime] = None
_LOCAL_TZ: datetime.tzinfo = datetime.timezone.utc


def set_local_timezone(tz: datetime.tzinfo) -> None:
    global _LOCAL_TZ
    _LOCAL_TZ = tz


def get_local_timezone() -> datetime.tzinfo:
    return _LOCAL_TZ


def get_current_date() -> datetime.datetime:
    """
    Returns the current local datetime matching JavaScript new Date() local time semantics.
    If frozen, converts the frozen datetime to the configured local timezone.
    """
    if _FROZEN_DATE is not None:
        if _FROZEN_DATE.tzinfo is not None:
            return _FROZEN_DATE.astimezone(_LOCAL_TZ)
        return _FROZEN_DATE.replace(tzinfo=_LOCAL_TZ)
    return datetime.datetime.now(_LOCAL_TZ)


# Backward-compatibility alias
get_current_utc_date = get_current_date


@contextmanager
def freeze_time(target: Union[str, datetime.datetime], tz_offset: Optional[Union[datetime.tzinfo, int, float, str]] = None):
    global _FROZEN_DATE, _LOCAL_TZ
    prev_date = _FROZEN_DATE
    prev_tz = _LOCAL_TZ

    if tz_offset is not None:
        if isinstance(tz_offset, datetime.tzinfo):
            _LOCAL_TZ = tz_offset
        elif isinstance(tz_offset, (int, float)):
            _LOCAL_TZ = datetime.timezone(datetime.timedelta(hours=tz_offset))
        elif isinstance(tz_offset, str):
            sign = 1 if tz_offset[0] == '+' else -1
            parts = tz_offset[1:].split(':')
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            _LOCAL_TZ = datetime.timezone(sign * datetime.timedelta(hours=h, minutes=m))

    if isinstance(target, str):
        if 'Z' in target:
            dt = datetime.datetime.fromisoformat(target.replace('Z', '+00:00'))
        else:
            dt = datetime.datetime.fromisoformat(target)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_LOCAL_TZ)
        _FROZEN_DATE = dt
    else:
        if target.tzinfo is None:
            target = target.replace(tzinfo=_LOCAL_TZ)
        _FROZEN_DATE = target

    try:
        yield get_current_date()
    finally:
        _FROZEN_DATE = prev_date
        _LOCAL_TZ = prev_tz
