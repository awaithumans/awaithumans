"""Internal types for the email channel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActionClaim:
    """The decoded contents of a magic-link token.

    Produced by `magic_links.verify_action_token`. Carries the task
    reference, the single field/value the link commits to, the
    expiry timestamp, the recipient email the link was issued to,
    and a unique `jti` (JWT-style ID) used by the consume table
    to enforce single-use semantics.

    `recipient` is the email address the renderer signed the link
    for — used by the action route to stamp `completed_by_email`
    on the task so the audit log isn't a black hole for email
    completions. None for tokens minted before this field was
    added (backward-compat with in-flight tokens at deploy time).
    """

    task_id: str
    field_name: str
    value: Any
    expires_at: int
    jti: str
    recipient: str | None = None
