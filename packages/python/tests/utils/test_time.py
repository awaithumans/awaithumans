"""Regression tests for `awaithumans.utils.time.to_utc_unix`.

The bug this defends against: `task.timeout_at` is written tz-aware
but comes back from SQLite naive. Calling `.timestamp()` directly on
the naive value made Python interpret it as LOCAL time and shift the
resulting Unix seconds by the local-UTC offset. For users east of UTC
(Lagos UTC+1, Mumbai UTC+5:30, Singapore UTC+8), this killed email-
handoff links at birth — a 10-minute task issued a URL whose `e`
parameter sat ~3,000+ seconds in the past on a UTC+1 machine.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from awaithumans.utils.time import to_utc_unix

pytestmark = pytest.mark.skipif(
    not hasattr(time, "tzset"),
    reason="time.tzset is POSIX-only; cannot force a non-UTC tz on Windows.",
)


@pytest.fixture
def lagos_tz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the test under TZ=Africa/Lagos (UTC+1, no DST).

    Same shape as the user environment where the bug was first
    reproduced. Restored after the test.
    """
    monkeypatch.setenv("TZ", "Africa/Lagos")
    time.tzset()
    yield
    time.tzset()


def test_naive_datetime_is_interpreted_as_utc(lagos_tz: None) -> None:
    """A naive datetime must round-trip to the same Unix seconds as the
    equivalent tz-aware UTC datetime, regardless of the local tz."""
    naive = datetime(2026, 5, 14, 22, 30, 0)  # represents UTC
    aware = datetime(2026, 5, 14, 22, 30, 0, tzinfo=timezone.utc)
    assert to_utc_unix(naive) == int(aware.timestamp())


def test_aware_datetime_round_trips_unchanged(lagos_tz: None) -> None:
    """Already-aware datetimes get the same answer as `.timestamp()`."""
    aware = datetime(2026, 5, 14, 22, 30, 0, tzinfo=timezone.utc)
    assert to_utc_unix(aware) == int(aware.timestamp())


def test_url_expiry_is_in_future_for_fresh_short_task(lagos_tz: None) -> None:
    """End-to-end shape: a 10-minute timeout produces an expiry that is
    actually in the future of `time.time()`. Without the fix, this
    sits ~3,000 s in the past on UTC+1 — link born expired."""
    now_aware = datetime.now(timezone.utc)
    # Simulate what comes back from SQLite: tz-stripped UTC.
    timeout_at_naive = (now_aware + timedelta(seconds=600)).replace(tzinfo=None)
    e = to_utc_unix(timeout_at_naive)
    assert e > int(time.time()), (
        f"Expiry {e} not after now {int(time.time())}; "
        "URL is born expired (reproduces the email-handoff bug)."
    )
