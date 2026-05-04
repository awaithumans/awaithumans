"""Block Kit renderer — public surface.

Callers should depend on these three symbols only. Per-category element
renderers live in sibling modules and are wired through `surfaces.py`.

Shape of the returned modal view matches
https://api.slack.com/reference/surfaces/views.
"""

from __future__ import annotations

from awaithumans.server.channels.slack.blocks.helpers import UnrenderableInSlackError
from awaithumans.server.channels.slack.blocks.surfaces import (
    claimed_message_blocks,
    form_to_modal,
    open_review_message_blocks,
    terminal_message_blocks,
)

__all__ = [
    "UnrenderableInSlackError",
    "claimed_message_blocks",
    "form_to_modal",
    "open_review_message_blocks",
    "terminal_message_blocks",
]
