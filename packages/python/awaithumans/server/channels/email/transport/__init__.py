"""Email transport backends.

Pick one via AWAITHUMANS_EMAIL_TRANSPORT (or per-identity `transport`):

- resend   — Resend (managed, API key)
- smtp     — any SMTP server (Google Workspace, Office 365, self-hosted)
- logging  — prints to stdout. Dev only.
- noop     — silently drops. Tests.

All backends conform to `EmailTransport` (transport/base.py).
"""

from __future__ import annotations

from awaithumans.server.channels.email.transport.base import (
    EmailMessage,
    EmailSendResult,
    EmailTransport,
    EmailTransportError,
)
from awaithumans.server.channels.email.transport.factory import resolve_transport

__all__ = [
    "EmailMessage",
    "EmailSendResult",
    "EmailTransport",
    "EmailTransportError",
    "resolve_transport",
]
