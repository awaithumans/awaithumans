"""In-process sliding-window rate limiter.

Used to put a ceiling on login + first-run-setup attempts. argon2id
costs ~100ms per `verify_password` call, so unbounded brute force is
already CPU-expensive — but the unauthenticated `/api/setup/operator`
endpoint can be ground at line-rate during the first-run window
(which can stretch from minutes to days while the operator pastes the
token), and credential stuffing across many emails bypasses the
per-email argon2 cost.

Design choices:

  - **In-process only.** Single-uvicorn-worker self-hosted servers are
    the v1 target; nothing here would help across workers without a
    shared store (Redis, Postgres). When we go multi-worker, swap
    this implementation behind the same `check()` contract.
  - **Sliding-window counter, not token bucket.** Simpler to reason
    about for "5 attempts per minute" semantics. The cost is a tiny
    bit of bookkeeping per key (a list of timestamps).
  - **No bans / lockouts.** A "lock the account after N failures"
    feature lets an attacker trivially deny service to a known
    target by spraying their email. Operators recover from rate
    limits by waiting; from lockouts only by admin intervention.
  - **Thread-safe via `threading.Lock`.** Async routes share state
    across event-loop tasks AND, on some setups, across worker
    threads (Starlette's BackgroundTasks). Lock is held only over
    the dict mutation — no I/O inside.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class RateLimiter:
    """Sliding-window counter. Allows up to `limit` events per `window`
    seconds for any single key.

    `check(key)` is the only side-effecting call: it bumps the counter
    if the key is under-limit and returns True, or returns False
    without bumping when the limit is reached. Callers should treat a
    False return as "send 429 to the user" and not retry the bump.

    `reset(key)` is for tests and for the success path on login —
    once a user authenticates successfully, we forget their failure
    count so they don't get throttled by their own typo history."""

    def __init__(self, *, limit: int, window_seconds: float) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """Try to record one event for `key`. Returns True if allowed,
        False if the limit is already at or above `self.limit` within
        the current window."""
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            hits = self._hits[key]
            # In-place trim — keeps memory bounded by sum of active
            # keys' window-counts rather than ever-growing history.
            i = 0
            for t in hits:
                if t > cutoff:
                    break
                i += 1
            if i:
                del hits[:i]
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def reset(self, key: str) -> None:
        """Forget any recorded hits for `key`. Used after a successful
        login so a legit user's earlier typos don't accumulate."""
        with self._lock:
            self._hits.pop(key, None)


# Module-level singletons. Chosen so the same limiter persists across
# requests within a process — instantiating per-request would defeat
# the whole point.
#
# Login: per-IP gate is tight (covers credential stuffing from one
# host); per-email gate stays open longer because a real user retrying
# their password might trigger the IP gate first.
LOGIN_PER_IP = RateLimiter(limit=10, window_seconds=300)
LOGIN_PER_EMAIL = RateLimiter(limit=20, window_seconds=300)

# Setup: rare flow but unauthenticated — be generous enough that a
# fumbling first-run operator doesn't lock themselves out, tight
# enough that an attacker grinding the bootstrap token can't burn
# more than ~30/5min.
SETUP_PER_IP = RateLimiter(limit=30, window_seconds=300)


def client_ip(request) -> str:  # type: ignore[no-untyped-def]
    """Best-effort client IP for rate-limit keying.

    `request.client.host` is what Starlette parses from the socket
    peer — for self-hosted uvicorn that's the real client when no
    proxy is in front. Operators behind a proxy should set their
    proxy to overwrite `X-Forwarded-For` to something they trust,
    then run uvicorn with `--proxy-headers` so `request.client.host`
    reflects it.

    Falling back to "unknown" rather than raising means a request
    without a parseable peer (rare — synthetic test clients, some
    edge cases) just shares a single rate-limit bucket. Acceptable;
    the alternative is a soft-DOS against legit unknowns."""
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
