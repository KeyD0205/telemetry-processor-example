from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

NANOSECONDS_PER_SECOND = 1_000_000_000


def timestamp_ns_from_event_time(event_time: Mapping[str, Any]) -> int:
    sec = int(event_time.get("sec", 0))
    nanosec = int(event_time.get("nanosec", 0))
    if nanosec < 0 or nanosec >= NANOSECONDS_PER_SECOND:
        raise ValueError(f"nanosec must be in [0, {NANOSECONDS_PER_SECOND}); got {nanosec}")
    return sec * NANOSECONDS_PER_SECOND + nanosec


def datetime_from_ns(timestamp_ns: int) -> datetime:
    sec, ns = divmod(timestamp_ns, NANOSECONDS_PER_SECOND)
    return datetime.fromtimestamp(sec + ns / NANOSECONDS_PER_SECOND, tz=timezone.utc)


def iso_from_ns(timestamp_ns: int) -> str:
    return datetime_from_ns(timestamp_ns).isoformat().replace("+00:00", "Z")
