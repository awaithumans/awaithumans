"""Short-text and long-text element renderers.

DisplayText (read-only markdown) is not an input element — it's handled
directly in the surfaces dispatcher.
"""

from __future__ import annotations

from typing import Any

from awaithumans.forms.fields.text import LongText, ShortText
from awaithumans.server.channels.slack.blocks.helpers import truncate

# Slack's placeholder text caps at 150 chars.
_PLACEHOLDER_MAX = 150

# Slack text-input subtype → Block Kit element type. Fall back to
# plain_text_input when no typed element exists.
_SUBTYPE_TO_ELEMENT = {
    "email": "email_text_input",
    "url": "url_text_input",
    "number": "number_input",
    "currency": "number_input",
}


def short_text_element(field: ShortText) -> dict[str, Any]:
    elem_type = _SUBTYPE_TO_ELEMENT.get(field.subtype, "plain_text_input")
    elem: dict[str, Any] = {"type": elem_type, "action_id": field.name}
    if field.placeholder:
        elem["placeholder"] = {
            "type": "plain_text",
            "text": truncate(field.placeholder, _PLACEHOLDER_MAX),
        }
    if field.min_length:
        elem["min_length"] = field.min_length
    if field.max_length:
        elem["max_length"] = field.max_length
    if elem_type == "number_input":
        elem["is_decimal_allowed"] = field.subtype == "currency"
    return elem


def long_text_element(field: LongText) -> dict[str, Any]:
    elem: dict[str, Any] = {
        "type": "plain_text_input",
        "action_id": field.name,
        "multiline": True,
    }
    if field.placeholder:
        elem["placeholder"] = {
            "type": "plain_text",
            "text": truncate(field.placeholder, _PLACEHOLDER_MAX),
        }
    if field.min_length:
        elem["min_length"] = field.min_length
    if field.max_length:
        elem["max_length"] = field.max_length
    return elem
