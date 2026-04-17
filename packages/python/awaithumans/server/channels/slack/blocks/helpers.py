"""Shared Block Kit helpers: truncation, option wrapper, input-block wrapper.

`UnrenderableInSlackError` lives here rather than with the dispatcher so
importers can catch it without pulling in the full element-renderer set.
"""

from __future__ import annotations

from typing import Any

from awaithumans.utils.constants import SLACK_BLOCK_ID_PREFIX


class UnrenderableInSlackError(Exception):
    """Raised when a form contains primitives that can't render in Slack.

    Callers should check `form_renders_in(form, 'slack')` BEFORE calling
    `form_to_modal` to avoid this exception in production.
    """


# Slack's option text caps at 75 chars per Block Kit spec.
_OPTION_LABEL_MAX = 75

# Slack's block-level hint caps at 2000 chars.
_HINT_MAX = 2000


def truncate(s: str, max_len: int) -> str:
    """Truncate a string with an ellipsis when it exceeds `max_len`."""
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def option(value: str, label: str) -> dict[str, Any]:
    """Build a Block Kit `option` dict for select/radio/checkbox elements."""
    return {
        "value": value,
        "text": {"type": "plain_text", "text": truncate(label, _OPTION_LABEL_MAX)},
    }


def input_block(field: Any, element: dict[str, Any]) -> dict[str, Any]:
    """Wrap a Block Kit input-element in a full `input` block.

    Carries the field's label, required flag, and hint. `block_id` is
    prefixed so view_submission handlers can identify our blocks and
    extract the field name deterministically.
    """
    block: dict[str, Any] = {
        "type": "input",
        "block_id": f"{SLACK_BLOCK_ID_PREFIX}{field.name}",
        "label": {"type": "plain_text", "text": field.label or field.name},
        "optional": not field.required,
        "element": element,
    }
    if field.hint:
        block["hint"] = {"type": "plain_text", "text": truncate(field.hint, _HINT_MAX)}
    return block
