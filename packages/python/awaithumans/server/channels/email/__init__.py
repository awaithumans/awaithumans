"""Email channel — transport abstraction + renderer + magic-link actions.

Public API:

    from awaithumans.server.channels.email import (
        notify_task,
        sign_action_token,
        verify_action_token,
    )
"""

from __future__ import annotations

from awaithumans.server.channels.email.magic_links import (
    sign_action_token,
    verify_action_token,
)
from awaithumans.server.channels.email.notifier import notify_task

__all__ = [
    "notify_task",
    "sign_action_token",
    "verify_action_token",
]
