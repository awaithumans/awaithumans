"""Types for the Slack-handoff URL builder.

Lives in its own module so consumers (notifier, claim flow, post-
completion updater) can import the lightweight dataclass without
pulling in `cryptography` and the rest of the signing path.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HandoffParams:
    """Inputs for the recipient-bound part of a handoff URL.

    `user_id` is the directory user we're issuing the link to — the
    server will mint a session for THIS user when the URL is clicked.
    `exp_unix` is the absolute Unix timestamp the link stops working;
    typically `task.timeout_at` so the link lives as long as the task
    is actionable.
    """

    user_id: str
    exp_unix: int
