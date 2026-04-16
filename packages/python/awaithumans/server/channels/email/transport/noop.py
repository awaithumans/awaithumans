"""No-op transport — silently drops every message.

For tests. Returns a stable-looking message_id so assertions can check
`result.transport == "noop"` and inspect it.
"""

from __future__ import annotations

import uuid

from awaithumans.server.channels.email.transport.base import (
    EmailMessage,
    EmailSendResult,
)


class NoopTransport:
    """Discard every message. Records nothing."""

    @property
    def name(self) -> str:
        return "noop"

    async def send(self, message: EmailMessage) -> EmailSendResult:
        return EmailSendResult(
            message_id=f"noop-{uuid.uuid4().hex[:16]}",
            transport=self.name,
        )
