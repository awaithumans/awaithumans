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
import sys
import threading

logger = logging.getLogger("awaithumans.server.core.bootstrap")

_BOOTSTRAP_TOKEN_BYTES = 32

# ANSI escape codes. Empty strings when not writing to a TTY so the
# banner still reads cleanly in logs, CI output, Docker compose, etc.
_ANSI_RESET = "\033[0m"
_ANSI_BOLD = "\033[1m"
_ANSI_GREEN = "\033[32m"
_ANSI_DIM = "\033[2m"

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
    """Print the first-run setup URL to stdout in a visually dominant
    format — uncolored fallback when stdout isn't a TTY (CI, Docker).

    Writes directly to stdout instead of going through the logger. The
    banner has to survive log-level filters, piped redirection
    (`awaithumans dev > log.txt`), and any operator who skims past
    alembic chatter. Logger output can be suppressed; a direct stdout
    write can't.

    The URL already contains the token — operators copy the whole
    line into their browser. The wording says "Copy this URL" so no
    one mistakes the token for a placeholder.
    """
    use_color = sys.stdout.isatty()
    bold = _ANSI_BOLD if use_color else ""
    green = _ANSI_GREEN if use_color else ""
    dim = _ANSI_DIM if use_color else ""
    reset = _ANSI_RESET if use_color else ""

    width = 72
    divider = "═" * width

    lines = [
        "",
        "",
        f"{bold}{divider}{reset}",
        f"  {bold}First-run setup — create your operator account{reset}",
        "",
        "  Open this URL in your browser:",
        "",
        f"    {green}{bold}{setup_url}{reset}",
        "",
        f"  {dim}(Contains a single-use token. Restart the server for a fresh one.){reset}",
        f"{bold}{divider}{reset}",
        "",
        "",
    ]
    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()

    # Also emit to the logger at WARNING level — without color — so
    # anyone following logs via journalctl / Docker logs still sees
    # the URL even if stdout was redirected. The duplicate is cheap.
    logger.warning("First-run setup URL (copy into a browser): %s", setup_url)
