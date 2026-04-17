"""Email template renderers.

Each function loads a `.html` or `.txt` file from the sibling `html/`
directory and substitutes variables using `string.Template`. Loops
(payload rows, buttons) are pre-rendered in Python and substituted as
HTML fragments — `string.Template` has no loop syntax and doesn't need
one here.

All string inputs from callers MUST already be trusted or pre-escaped.
This module escapes URLs and free-text values before substitution.
"""

from __future__ import annotations

from functools import cache
from html import escape
from importlib import resources
from string import Template

from awaithumans.server.channels.email.templates.palette import (
    DARK_PALETTE,
    FONT_STACK,
    LIGHT_PALETTE,
    ButtonSpec,
    render_button,
)


@cache
def _load(name: str) -> Template:
    """Load a template file once and cache it."""
    text = resources.files(
        "awaithumans.server.channels.email.templates"
    ).joinpath("html", name).read_text(encoding="utf-8")
    return Template(text)


def notification_html(
    *,
    task_title: str,
    payload_lines: list[tuple[str, str]],
    redacted: bool,
    buttons: list[ButtonSpec],
    review_url: str,
) -> str:
    """The primary email: task title, payload preview, buttons, link-out footer."""
    payload_html = _render_payload_html(payload_lines, redacted)
    buttons_inner = "".join(render_button(b) for b in buttons)
    buttons_section = (
        f'<div style="margin:24px 0;">{buttons_inner}</div>' if buttons else ""
    )

    return _load("notification.html").substitute(
        task_title=escape(task_title),
        review_url=escape(review_url, quote=True),
        payload_html=payload_html,
        buttons_section=buttons_section,
        font_stack=FONT_STACK,
        **LIGHT_PALETTE,
    )


def notification_text(
    *,
    task_title: str,
    payload_lines: list[tuple[str, str]],
    redacted: bool,
    buttons: list[ButtonSpec],
    review_url: str,
) -> str:
    """Plain-text alternate. Deliverability helper + accessibility."""
    payload_block = (
        "Payload redacted."
        if redacted
        else "\n".join(f"  {k}: {v}" for k, v in payload_lines)
    )
    buttons_block = (
        "Respond:\n" + "\n".join(f"  {b.label}: {b.url}" for b in buttons) + "\n"
        if buttons
        else ""
    )
    return _load("notification.txt").substitute(
        task_title=task_title,
        payload_block=payload_block,
        buttons_block=buttons_block,
        review_url=review_url,
    )


def confirmation_page_html(
    *,
    task_title: str,
    action_label: str,
    post_url: str,
    cancel_url: str,
) -> str:
    """The 'Are you sure?' page the magic link lands on (GET)."""
    return _load("confirmation_page.html").substitute(
        task_title=escape(task_title),
        action_label=escape(action_label),
        post_url=escape(post_url, quote=True),
        cancel_url=escape(cancel_url, quote=True),
        font_stack=FONT_STACK,
        **DARK_PALETTE,
    )


def completed_page_html(*, message: str) -> str:
    """Shown after POST succeeds or when the task is already terminal."""
    return _load("completed_page.html").substitute(
        message=escape(message),
        font_stack=FONT_STACK,
        **DARK_PALETTE,
    )


# ─── Internal fragment builders ─────────────────────────────────────────


def _render_payload_html(
    payload_lines: list[tuple[str, str]],
    redacted: bool,
) -> str:
    """Build the payload-preview fragment for the notification email."""
    if redacted:
        return (
            '<p style="color:#555;font-size:13px;">'
            "<em>Payload redacted.</em></p>"
        )
    if not payload_lines:
        return ""
    rows = "".join(
        f'<tr><td style="color:#6B7280;font-size:13px;padding:3px 12px 3px 0;'
        f'vertical-align:top;"><strong>{escape(key)}</strong></td>'
        f'<td style="color:#111827;font-size:13px;padding:3px 0;'
        f'word-break:break-word;">{escape(val)}</td></tr>'
        for key, val in payload_lines
    )
    return (
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:16px 0;">{rows}</table>'
    )
