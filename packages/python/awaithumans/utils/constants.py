"""Project-wide constants.

All magic numbers, configuration defaults, and shared values live here.
Import from here, not from individual modules.
"""

from __future__ import annotations

from awaithumans.types import TaskStatus

# ─── Project Identity ────────────────────────────────────────────────────

SERVICE_NAME = "awaithumans"
DOCS_BASE_URL = "https://awaithumans.dev/docs/troubleshooting"

# ─── Timeout ─────────────────────────────────────────────────────────────

MIN_TIMEOUT_SECONDS = 60          # 1 minute — minimum allowed timeout
MAX_TIMEOUT_SECONDS = 2_592_000   # 30 days — maximum allowed timeout

# ─── Long-Poll ───────────────────────────────────────────────────────────

POLL_INTERVAL_SECONDS = 25        # reconnection interval, must stay under gateway timeouts (60s)

# ─── Timeout Scheduler ───────────────────────────────────────────────────

TIMEOUT_CHECK_INTERVAL_SECONDS = 5  # how often the scheduler checks for expired tasks

# ─── Task Status Sets ────────────────────────────────────────────────────

TERMINAL_STATUSES_SET = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.TIMED_OUT,
    TaskStatus.CANCELLED,
    TaskStatus.VERIFICATION_EXHAUSTED,
})

# ─── Payload ─────────────────────────────────────────────────────────────

MAX_PAYLOAD_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB hard limit
