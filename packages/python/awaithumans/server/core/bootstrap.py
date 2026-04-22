"""First-run bootstrap token.

On startup, if the `users` table is empty, a random token is generated
and logged prominently. The operator visits `/setup?token=<TOKEN>`,
submits email + password, and becomes the first user (role=operator).
After that, `/api/setup/*` routes always return 410 Gone — the
bootstrap is a one-shot.

Token lives only in process memory. Restarts regenerate it as long as
no user exists yet; once setup completes, the token is cleared and
stays cleared for the process lifetime.

Why in-memory (not DB):
- Bootstrap credentials shouldn't outlive a process crash. If the
  operator walks away from setup, a restart gives them a fresh
  token — no stale creds to recover.
- Zero persistence ≠ zero operational burden: restart before setup
  reveals the new token in the log.

Why not email magic link:
- Needs email transport configured, which is circular — email
  identities are managed through the same admin API the operator
  is about to set up.

Concurrency:
- Module-level `_lock` keeps the generator idempotent if two
  startup paths call `ensure_token` concurrently. The token is
  generated exactly once per empty-DB process.
"""

from __future__ import annotations

import hmac
import logging
import secrets
import threading

logger = logging.getLogger("awaithumans.server.core.bootstrap")

_BOOTSTRAP_TOKEN_BYTES = 32

_lock = threading.Lock()
_token: str | None = None
_completed: bool = False


def ensure_token() -> str:
    """Return the current bootstrap token, generating one if needed.
    Idempotent. Raises RuntimeError if setup has already completed."""
    global _token
    with _lock:
        if _completed:
            raise RuntimeError("Bootstrap already completed in this process.")
        if _token is None:
            _token = secrets.token_urlsafe(_BOOTSTRAP_TOKEN_BYTES)
        return _token


def verify_token(supplied: str) -> bool:
    """Constant-time compare. Returns False if the token hasn't been
    generated yet (setup not needed) or setup already completed."""
    with _lock:
        if _completed or _token is None:
            return False
        return hmac.compare_digest(supplied, _token)


def mark_complete() -> None:
    """Called after the first operator is created. Invalidates the
    token permanently for this process."""
    global _token, _completed
    with _lock:
        _completed = True
        _token = None


def is_active() -> bool:
    """True when a token is live and can complete setup. False after
    completion or before `ensure_token` runs."""
    with _lock:
        return _token is not None and not _completed


def log_setup_banner(setup_url: str) -> None:
    """Emit the first-run setup URL to the log in a visually loud
    format. Called at startup when count_users == 0 so operators
    can't miss it in the server output.
    """
    banner = "━" * 60
    logger.warning("\n%s\nFirst-run setup:\n  → %s\n%s\n", banner, setup_url, banner)
