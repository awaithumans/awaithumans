"""Logging transport — prints the rendered email to stdout.

For local development. Never use in production: mail is not actually sent.
`AWAITHUMANS_EMAIL_TRANSPORT=logging` picks this.
"""

from __future__ import annotations

import logging
import uuid

from awaithumans.server.channels.email.transport.base import (
    EmailMessage,
    EmailSendResult,
)

logger = logging.getLogger("awaithumans.server.channels.email.transport.logging")


class LoggingTransport:
    @property
    def name(self) -> str:
        return "logging"

    async def send(self, message: EmailMessage) -> EmailSendResult:
        logger.info(
            "[email/logging] to=%s from=%s subject=%s",
            message.to,
            message.formatted_from(),
            message.subject,
        )
        logger.info("[email/logging] text body:\n%s", message.text)
        return EmailSendResult(
            message_id=f"logging-{uuid.uuid4().hex[:16]}",
            transport=self.name,
        )
