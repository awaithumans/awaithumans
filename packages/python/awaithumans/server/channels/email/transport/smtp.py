"""SMTP transport — aiosmtplib.

Covers Google Workspace (smtp.gmail.com:587), Office 365
(smtp.office365.com:587), and any self-hosted/relay SMTP server.
Auth is username + password (app password for Gmail / O365).

STARTTLS on 587 is the default. For implicit TLS (port 465), pass
`use_tls=True`. Plain SMTP without TLS is allowed but warned against —
operators shouldn't be sending mail over cleartext in 2026.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage as MIMEMessage

import aiosmtplib

from awaithumans.server.channels.email.transport.base import (
    EmailMessage,
    EmailSendResult,
    EmailTransportError,
)

logger = logging.getLogger("awaithumans.server.channels.email.transport.smtp")


class SMTPTransport:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        start_tls: bool = True,
    ) -> None:
        if not host:
            raise EmailTransportError("SMTP transport requires a host.")
        if use_tls and start_tls:
            # aiosmtplib rejects this — one handshake mode at a time.
            start_tls = False
        if not use_tls and not start_tls:
            logger.warning(
                "SMTP transport for %s:%d is configured without TLS. "
                "Credentials and message content will transit in cleartext.",
                host,
                port,
            )
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._start_tls = start_tls

    @property
    def name(self) -> str:
        return "smtp"

    async def send(self, message: EmailMessage) -> EmailSendResult:
        mime = _to_mime(message)
        try:
            # aiosmtplib.send handles connect + EHLO + STARTTLS + AUTH + MAIL/RCPT/DATA + QUIT.
            errors, response = await aiosmtplib.send(
                mime,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                use_tls=self._use_tls,
                start_tls=self._start_tls,
            )
        except (aiosmtplib.SMTPException, OSError) as exc:
            raise EmailTransportError(f"SMTP send failed: {exc}") from exc

        if errors:
            raise EmailTransportError(f"SMTP rejected recipients: {errors}")

        # aiosmtplib doesn't give us a Message-ID unless the server echoes one.
        # Python's EmailMessage auto-generates one when we don't set it — grab it.
        return EmailSendResult(
            message_id=str(mime.get("Message-ID") or "").strip("<>") or None,
            transport=self.name,
        )


def _to_mime(msg: EmailMessage) -> MIMEMessage:
    """Build a multipart/alternative MIME message from our EmailMessage."""
    mime = MIMEMessage()
    mime["From"] = msg.formatted_from()
    mime["To"] = msg.to
    mime["Subject"] = msg.subject
    if msg.reply_to:
        mime["Reply-To"] = msg.reply_to
    # Auto-generate Message-ID so we can return it from send().
    from email.utils import make_msgid

    mime["Message-ID"] = make_msgid()

    mime.set_content(msg.text)
    mime.add_alternative(msg.html, subtype="html")
    return mime
