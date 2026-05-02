"""Internal types for the email channel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActionClaim:
    """The decoded contents of a magic-link token.

    Produced by `magic_links.verify_action_token`. Carries the task
    reference, the single field/value the link commits to, the
    expiry timestamp, and a unique `jti` (JWT-style ID) used by the
    consume table to enforce single-use semantics.
    """

    task_id: str
    field_name: str
    value: Any
    expires_at: int
    jti: str
