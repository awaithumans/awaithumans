"""Resolve a transport from either env config or a DB identity row.

Two entry points:

- `resolve_default_transport()` — reads `AWAITHUMANS_EMAIL_*` env vars.
  Used when a task's notify entry has no `+identity` suffix.
- `resolve_identity_transport(identity)` — reads the encrypted
  transport_config blob off a DB identity row.

Both return None when the relevant config is missing, so the notifier
can log-and-skip instead of raising.
"""

from __future__ import annotations

import logging
from typing import Any

from awaithumans.server.channels.email.transport.base import (
    EmailTransport,
    EmailTransportError,
)
from awaithumans.server.channels.email.transport.file import FileTransport
from awaithumans.server.channels.email.transport.logging import LoggingTransport
from awaithumans.server.channels.email.transport.noop import NoopTransport
from awaithumans.server.channels.email.transport.resend import ResendTransport
from awaithumans.server.channels.email.transport.smtp import SMTPTransport
from awaithumans.server.core.config import settings
from awaithumans.server.db.models import EmailSenderIdentity
from awaithumans.server.services.email_identity_service import identity_config

logger = logging.getLogger("awaithumans.server.channels.email.transport.factory")


def resolve_transport(name: str, config: dict[str, Any]) -> EmailTransport:
    """Build a transport from its string name + a config dict.

    Raises EmailTransportError if the transport name is unknown or
    required config is missing.
    """
    name = (name or "").lower()

    if name == "resend":
        api_key = config.get("api_key")
        if not api_key:
            raise EmailTransportError("resend transport: config.api_key is required.")
        return ResendTransport(api_key=api_key)

    if name == "smtp":
        host = config.get("host")
        port = int(config.get("port") or 587)
        if not host:
            raise EmailTransportError("smtp transport: config.host is required.")
        # Accept `user` as an alias for `username`. The dashboard's
        # Email-identity form hint advertises `user`, Python's stdlib
        # smtplib uses `user` too — silently dropping it on the floor
        # left users with unauthenticated SMTP and no signal.
        username = config.get("username") or config.get("user")
        # Port 465 is implicit-TLS; default `use_tls` to True there
        # unless explicitly overridden. STARTTLS on 465 fails the
        # handshake, which is the exact trap most operators hit on
        # the first send. Matches the convention every mature SMTP
        # library (aiosmtplib, smtplib, Nodemailer, etc.) uses.
        use_tls = bool(config["use_tls"]) if "use_tls" in config else port == 465
        return SMTPTransport(
            host=host,
            port=port,
            username=username,
            password=config.get("password"),
            use_tls=use_tls,
            start_tls=bool(config.get("start_tls", True)),
        )

    if name == "logging":
        return LoggingTransport()

    if name == "noop":
        return NoopTransport()

    if name == "file":
        directory = config.get("dir")
        if not directory:
            raise EmailTransportError("file transport: config.dir is required.")
        return FileTransport(dir=directory)

    raise EmailTransportError(
        f"Unknown email transport: '{name}'. Valid: resend, smtp, logging, noop, file."
    )


def resolve_default_transport() -> EmailTransport | None:
    """Build a transport from env vars. Returns None if unconfigured."""
    name = settings.EMAIL_TRANSPORT
    if not name:
        return None

    try:
        if name == "resend":
            return resolve_transport("resend", {"api_key": settings.RESEND_KEY})
        if name == "smtp":
            return resolve_transport(
                "smtp",
                {
                    "host": settings.SMTP_HOST,
                    "port": settings.SMTP_PORT,
                    "username": settings.SMTP_USER,
                    "password": settings.SMTP_PASSWORD,
                    "use_tls": settings.SMTP_USE_TLS,
                    "start_tls": settings.SMTP_START_TLS,
                },
            )
        return resolve_transport(name, {})
    except EmailTransportError as exc:
        logger.error("Default email transport misconfigured: %s", exc)
        return None


def resolve_identity_transport(
    identity: EmailSenderIdentity,
) -> EmailTransport | None:
    """Build a transport from a DB identity row. Returns None on failure."""
    try:
        return resolve_transport(identity.transport, identity_config(identity))
    except EmailTransportError as exc:
        logger.error(
            "Identity '%s' misconfigured (transport=%s): %s",
            identity.id,
            identity.transport,
            exc,
        )
        return None
