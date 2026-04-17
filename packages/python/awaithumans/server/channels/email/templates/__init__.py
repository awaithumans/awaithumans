"""Email template package — public surface.

Callers import the five symbols below and nothing else. HTML lives in
`html/*.html|.txt`; the email-specific color palette and `ButtonSpec`
live in `palette.py`; renderers (file loaders + substitution) live in
`renderers.py`.
"""

from __future__ import annotations

from awaithumans.server.channels.email.templates.palette import ButtonSpec
from awaithumans.server.channels.email.templates.renderers import (
    completed_page_html,
    confirmation_page_html,
    notification_html,
    notification_text,
)

__all__ = [
    "ButtonSpec",
    "completed_page_html",
    "confirmation_page_html",
    "notification_html",
    "notification_text",
]
