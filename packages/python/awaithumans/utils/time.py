"""Datetime utilities that defend against the naive-datetime / local-time
interpretation trap.

SQLModel + SQLite stores `datetime` columns without tz info. A value
written tz-aware comes back naive on read. Calling `.timestamp()`
directly on a naive datetime makes Python interpret it as LOCAL time,
silently shifting the resulting Unix seconds by the local-UTC offset.

For users east of UTC (Lagos UTC+1, Mumbai UTC+5:30, Singapore UTC+8),
this shifts email-handoff URL expiry into the PAST at creation time —
a freshly issued 10-minute link is born already expired by the local
offset. For users west of UTC, the URL lives longer than the task.
Both are wrong.

`to_utc_unix` performs the coercion every code path that hands a
DB-loaded datetime to `.timestamp()` should use.
"""

from __future__ import annotations

from datetime import datetime, timezone


def to_utc_unix(dt: datetime) -> int:
    """Return Unix seconds for `dt`, treating any naive value as UTC.

    Use this anywhere a datetime loaded from the DB feeds into a Unix
    timestamp that crosses a channel boundary (signed URL, webhook
    payload, etc.). Already-aware datetimes round-trip unchanged.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())
