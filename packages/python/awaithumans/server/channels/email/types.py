"""Internal types for the email channel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActionClaim:
    """The decoded contents of a magic-link token.

    Produced by `magic_links.verify_action_token`. Carries the task
    reference and the single field/value the link commits to, plus the
    expiry timestamp for logging/debugging.
    """

    task_id: str
    field_name: str
    value: Any
    expires_at: int
