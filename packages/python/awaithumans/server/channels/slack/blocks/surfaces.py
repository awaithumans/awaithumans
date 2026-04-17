"""Public Block Kit surfaces: the review modal and the link-out message.

The dispatcher `_field_to_blocks` routes each primitive to its category-
specific element renderer and wraps the result in an `input` block. Non-
input primitives (DisplayText, Divider, Section, Image) render as
top-level blocks directly.

Shape of the returned modal view matches
https://api.slack.com/reference/surfaces/views.
"""

from __future__ import annotations

from typing import Any

from awaithumans.forms import FormDefinition
from awaithumans.forms.fields.date_time import (
    DatePicker,
    DateTimePicker,
    TimePicker,
)
from awaithumans.forms.fields.layout import Divider, Section
from awaithumans.forms.fields.media import FileUpload, Image
from awaithumans.forms.fields.numeric import OpinionScale, Slider, StarRating
from awaithumans.forms.fields.selection import (
    MultiSelect,
    PictureChoice,
    SingleSelect,
    Switch,
)
from awaithumans.forms.fields.text import DisplayText, LongText, ShortText
from awaithumans.server.channels.slack.blocks.date_time import (
    date_element,
    datetime_element,
    time_element,
)
from awaithumans.server.channels.slack.blocks.helpers import (
    UnrenderableInSlackError,
    input_block,
    truncate,
)
from awaithumans.server.channels.slack.blocks.media import file_upload_element
from awaithumans.server.channels.slack.blocks.numeric import (
    opinion_scale_element,
    slider_element,
    star_rating_element,
)
from awaithumans.server.channels.slack.blocks.selection import (
    multi_select_element,
    picture_choice_element,
    single_select_element,
    switch_element,
)
from awaithumans.server.channels.slack.blocks.text import (
    long_text_element,
    short_text_element,
)
from awaithumans.utils.constants import (
    SLACK_CONTEXT_VALUE_MAX,
    SLACK_HEADER_TEXT_MAX,
    SLACK_MODAL_CALLBACK_ID,
    SLACK_PLAIN_TEXT_MAX,
)


def form_to_modal(
    *,
    form: FormDefinition,
    task_id: str,
    task_title: str,
    task_payload: dict[str, Any] | None,
    redact_payload: bool = False,
) -> dict[str, Any]:
    """Build a Block Kit modal view for a form.

    `task_id` is stored in `private_metadata` so the view_submission
    handler can look up the task without trusting the Slack-side state.
    """
    blocks: list[dict[str, Any]] = []

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": truncate(task_title, SLACK_HEADER_TEXT_MAX),
        },
    })

    if task_payload and not redact_payload:
        lines = [
            f"*{k}*: {truncate(str(v), SLACK_CONTEXT_VALUE_MAX)}"
            for k, v in task_payload.items()
        ]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        })
        blocks.append({"type": "divider"})

    for field in form.fields:
        blocks.extend(_field_to_blocks(field))

    return {
        "type": "modal",
        "callback_id": SLACK_MODAL_CALLBACK_ID,
        "title": {"type": "plain_text", "text": "Review task"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": task_id,
        "blocks": blocks,
    }


# Truncation for the task title in the link-out message. Slack renders
# sections as mrkdwn and handles long text, but we keep it short for
# notification surfaces where Slack truncates aggressively.
_MESSAGE_TITLE_MAX = 200


def open_review_message_blocks(
    *,
    task_id: str,
    task_title: str,
    review_url: str,
    open_button_action_id: str,
    unsupported_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Initial message posted to a channel/user when a task is created.

    Always includes a "Review in dashboard" link-out. If the form is
    fully Slack-renderable, also includes an "Open in Slack" button
    that triggers the interactivity webhook to open a modal.
    """
    text = f"*New task to review:* {truncate(task_title, _MESSAGE_TITLE_MAX)}"
    if unsupported_fields:
        text += (
            f"\n_Contains {len(unsupported_fields)} field(s) that must "
            "be completed in the dashboard._"
        )

    elements: list[dict[str, Any]] = []
    if not unsupported_fields:
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Open in Slack"},
            "style": "primary",
            "action_id": open_button_action_id,
            "value": task_id,
        })
    elements.append({
        "type": "button",
        "text": {"type": "plain_text", "text": "Review in dashboard"},
        "url": review_url,
        "action_id": "awaithumans.open_dashboard",
    })

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {"type": "actions", "elements": elements},
    ]


# ─── Dispatch ────────────────────────────────────────────────────────────


def _field_to_blocks(field: Any) -> list[dict[str, Any]]:
    """Render a single primitive as 1..N Block Kit blocks."""
    # Non-input primitives first — these render as top-level blocks.
    if isinstance(field, DisplayText):
        return [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": truncate(field.text, SLACK_PLAIN_TEXT_MAX),
            },
        }]
    if isinstance(field, Divider):
        return [{"type": "divider"}]
    if isinstance(field, Section):
        out: list[dict[str, Any]] = [{
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": truncate(field.title, SLACK_HEADER_TEXT_MAX),
            },
        }]
        if field.subtitle:
            out.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": field.subtitle}],
            })
        return out
    if isinstance(field, Image):
        return [{
            "type": "image",
            "image_url": field.url,
            "alt_text": field.alt or field.label or "image",
        }]

    # Input primitives — wrap each element in an `input` block.
    element_for_kind: dict[type, Any] = {
        Switch: switch_element,
        ShortText: short_text_element,
        LongText: long_text_element,
        SingleSelect: single_select_element,
        MultiSelect: multi_select_element,
        PictureChoice: picture_choice_element,
        DatePicker: date_element,
        DateTimePicker: datetime_element,
        TimePicker: time_element,
        Slider: slider_element,
        StarRating: star_rating_element,
        OpinionScale: opinion_scale_element,
        FileUpload: file_upload_element,
    }
    for kind, renderer in element_for_kind.items():
        if isinstance(field, kind):
            return [input_block(field, renderer(field))]

    raise UnrenderableInSlackError(
        f"Primitive '{field.kind}' has no native Slack renderer. "
        "Check form_renders_in(form, 'slack') before calling form_to_modal()."
    )
