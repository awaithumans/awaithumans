"""Primitive → Block Kit renderer.

Every form primitive maps to one (or occasionally several) Block Kit blocks.
The caller must first check `form_renders_in(form, "slack")` — if False, it
should send a "Review in dashboard" link-out message instead of opening a
modal. This renderer assumes every field in the form can be represented in
Slack natively; primitives without a Slack path raise UnrenderableInSlack.

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
from awaithumans.utils.constants import (
    SLACK_BLOCK_ID_PREFIX,
    SLACK_MODAL_CALLBACK_ID,
)

# Block Kit hard limits.
_HEADER_MAX = 150
_PLAIN_TEXT_MAX = 3000
_MAX_OPTIONS_PER_SELECT = 100


class UnrenderableInSlack(Exception):
    """Raised when a form contains primitives that can't render in Slack.

    Callers should check form_renders_in(form, 'slack') BEFORE calling
    form_to_modal to avoid this exception in production.
    """


# ─── Public ──────────────────────────────────────────────────────────────


def form_to_modal(
    *,
    form: FormDefinition,
    task_id: str,
    task_title: str,
    task_payload: dict[str, Any] | None,
    redact_payload: bool = False,
) -> dict[str, Any]:
    """Build a Block Kit modal view for a form.

    `task_id` is stored in `private_metadata` so the view_submission handler
    can look up the task without trusting the Slack-side state.
    """
    blocks: list[dict[str, Any]] = []

    # Title as header.
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": _truncate(task_title, _HEADER_MAX)},
    })

    # Payload as context (read-only).
    if task_payload and not redact_payload:
        lines = [f"*{k}*: {_truncate(str(v), 200)}" for k, v in task_payload.items()]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        })
        blocks.append({"type": "divider"})

    # Every field.
    for field in form.fields:
        rendered = _field_to_blocks(field)
        blocks.extend(rendered)

    return {
        "type": "modal",
        "callback_id": SLACK_MODAL_CALLBACK_ID,
        "title": {"type": "plain_text", "text": "Review task"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": task_id,
        "blocks": blocks,
    }


def open_review_message_blocks(
    *,
    task_id: str,
    task_title: str,
    review_url: str,
    open_button_action_id: str,
    unsupported_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Initial message posted to a channel/user when a task is created.

    Always includes a "Review in dashboard" link-out. If the form is fully
    Slack-renderable, also includes an "Open in Slack" button that triggers
    the interactivity webhook to open a modal.
    """
    text = f"*New task to review:* {_truncate(task_title, 200)}"
    if unsupported_fields:
        text += f"\n_Contains {len(unsupported_fields)} field(s) that must be completed in the dashboard._"

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
    if isinstance(field, DisplayText):
        return [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": _truncate(field.text, _PLAIN_TEXT_MAX)},
        }]
    if isinstance(field, Divider):
        return [{"type": "divider"}]
    if isinstance(field, Section):
        out: list[dict[str, Any]] = [{
            "type": "header",
            "text": {"type": "plain_text", "text": _truncate(field.title, _HEADER_MAX)},
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

    # Input primitives — wrap element in an `input` block.
    if isinstance(field, Switch):
        return [_input_block(field, _switch_element(field))]
    if isinstance(field, ShortText):
        return [_input_block(field, _short_text_element(field))]
    if isinstance(field, LongText):
        return [_input_block(field, _long_text_element(field))]
    if isinstance(field, SingleSelect):
        return [_input_block(field, _single_select_element(field))]
    if isinstance(field, MultiSelect):
        return [_input_block(field, _multi_select_element(field))]
    if isinstance(field, PictureChoice):
        return [_input_block(field, _picture_choice_element(field))]
    if isinstance(field, DatePicker):
        return [_input_block(field, _date_element(field))]
    if isinstance(field, DateTimePicker):
        return [_input_block(field, _datetime_element(field))]
    if isinstance(field, TimePicker):
        return [_input_block(field, _time_element(field))]
    if isinstance(field, Slider):
        return [_input_block(field, _slider_element(field))]
    if isinstance(field, StarRating):
        return [_input_block(field, _star_rating_element(field))]
    if isinstance(field, OpinionScale):
        return [_input_block(field, _opinion_scale_element(field))]
    if isinstance(field, FileUpload):
        return [_input_block(field, _file_upload_element(field))]

    raise UnrenderableInSlack(
        f"Primitive '{field.kind}' has no native Slack renderer. "
        "Check form_renders_in(form, 'slack') before calling form_to_modal()."
    )


# ─── Input block wrapper ────────────────────────────────────────────────


def _input_block(field: Any, element: dict[str, Any]) -> dict[str, Any]:
    block: dict[str, Any] = {
        "type": "input",
        "block_id": f"{SLACK_BLOCK_ID_PREFIX}{field.name}",
        "label": {"type": "plain_text", "text": field.label or field.name},
        "optional": not field.required,
        "element": element,
    }
    if field.hint:
        block["hint"] = {"type": "plain_text", "text": _truncate(field.hint, 2000)}
    return block


# ─── Element builders ───────────────────────────────────────────────────


def _switch_element(field: Switch) -> dict[str, Any]:
    options = [
        {"text": {"type": "plain_text", "text": field.true_label}, "value": "true"},
        {"text": {"type": "plain_text", "text": field.false_label}, "value": "false"},
    ]
    elem: dict[str, Any] = {
        "type": "radio_buttons",
        "action_id": field.name,
        "options": options,
    }
    if field.default is True:
        elem["initial_option"] = options[0]
    elif field.default is False:
        elem["initial_option"] = options[1]
    return elem


def _short_text_element(field: ShortText) -> dict[str, Any]:
    # Slack has typed input elements for a few common subtypes; fall back
    # to plain_text_input + pattern otherwise.
    type_map = {
        "email": "email_text_input",
        "url": "url_text_input",
        "number": "number_input",
        "currency": "number_input",
    }
    elem_type = type_map.get(field.subtype, "plain_text_input")
    elem: dict[str, Any] = {"type": elem_type, "action_id": field.name}
    if field.placeholder:
        elem["placeholder"] = {"type": "plain_text", "text": _truncate(field.placeholder, 150)}
    if field.min_length:
        elem["min_length"] = field.min_length
    if field.max_length:
        elem["max_length"] = field.max_length
    if elem_type == "number_input":
        elem["is_decimal_allowed"] = field.subtype == "currency"
    return elem


def _long_text_element(field: LongText) -> dict[str, Any]:
    elem: dict[str, Any] = {
        "type": "plain_text_input",
        "action_id": field.name,
        "multiline": True,
    }
    if field.placeholder:
        elem["placeholder"] = {"type": "plain_text", "text": _truncate(field.placeholder, 150)}
    if field.min_length:
        elem["min_length"] = field.min_length
    if field.max_length:
        elem["max_length"] = field.max_length
    return elem


def _single_select_element(field: SingleSelect) -> dict[str, Any]:
    options = [_option(o.value, o.label) for o in field.options[:_MAX_OPTIONS_PER_SELECT]]
    # Under 4 options → radio buttons (better UX). Otherwise dropdown.
    if len(options) <= 4:
        elem: dict[str, Any] = {
            "type": "radio_buttons",
            "action_id": field.name,
            "options": options,
        }
    else:
        elem = {
            "type": "static_select",
            "action_id": field.name,
            "options": options,
            "placeholder": {"type": "plain_text", "text": "Select…"},
        }
    if field.default:
        match = next((o for o in options if o["value"] == field.default), None)
        if match:
            elem["initial_option"] = match
    return elem


def _multi_select_element(field: MultiSelect) -> dict[str, Any]:
    options = [_option(o.value, o.label) for o in field.options[:_MAX_OPTIONS_PER_SELECT]]
    # Under 10 options → checkboxes. Otherwise multi_static_select.
    if len(options) <= 10:
        elem: dict[str, Any] = {
            "type": "checkboxes",
            "action_id": field.name,
            "options": options,
        }
    else:
        elem = {
            "type": "multi_static_select",
            "action_id": field.name,
            "options": options,
            "placeholder": {"type": "plain_text", "text": "Select…"},
        }
    defaults = [o for o in options if o["value"] in field.default]
    if defaults:
        elem["initial_options"] = defaults
    return elem


def _picture_choice_element(field: PictureChoice) -> dict[str, Any]:
    # Slack radio buttons don't support images in options. Fall back to a
    # static_select so the label still carries the meaning.
    options = [_option(o.value, o.label) for o in field.options[:_MAX_OPTIONS_PER_SELECT]]
    elem_type = "multi_static_select" if field.multiple else "static_select"
    elem: dict[str, Any] = {
        "type": elem_type,
        "action_id": field.name,
        "options": options,
        "placeholder": {"type": "plain_text", "text": "Select…"},
    }
    return elem


def _date_element(field: DatePicker) -> dict[str, Any]:
    elem: dict[str, Any] = {"type": "datepicker", "action_id": field.name}
    if field.default:
        elem["initial_date"] = field.default
    return elem


def _datetime_element(field: DateTimePicker) -> dict[str, Any]:
    # Slack's datetimepicker takes an epoch int. Default skipped for simplicity.
    return {"type": "datetimepicker", "action_id": field.name}


def _time_element(field: TimePicker) -> dict[str, Any]:
    elem: dict[str, Any] = {"type": "timepicker", "action_id": field.name}
    if field.default:
        elem["initial_time"] = field.default
    return elem


def _slider_element(field: Slider) -> dict[str, Any]:
    # Slack has no slider. Render as number_input with min/max.
    elem: dict[str, Any] = {
        "type": "number_input",
        "action_id": field.name,
        "is_decimal_allowed": field.step < 1,
        "min_value": str(field.min),
        "max_value": str(field.max),
    }
    if field.default is not None:
        elem["initial_value"] = str(field.default)
    return elem


def _star_rating_element(field: StarRating) -> dict[str, Any]:
    options = [
        _option(str(v), "★" * v + "☆" * (field.max - v))
        for v in range(1, field.max + 1)
    ]
    elem: dict[str, Any] = {
        "type": "static_select",
        "action_id": field.name,
        "options": options,
    }
    if field.default:
        match = next((o for o in options if o["value"] == str(field.default)), None)
        if match:
            elem["initial_option"] = match
    return elem


def _opinion_scale_element(field: OpinionScale) -> dict[str, Any]:
    values = list(range(field.min, field.max + 1))
    labels_suffix = ""
    if field.min_label and field.max_label:
        labels_suffix = f" ({field.min_label} → {field.max_label})"
    options = [_option(str(v), f"{v}{labels_suffix if v == field.min else ''}") for v in values]
    elem: dict[str, Any] = {
        "type": "static_select",
        "action_id": field.name,
        "options": options,
    }
    if field.default is not None:
        match = next((o for o in options if o["value"] == str(field.default)), None)
        if match:
            elem["initial_option"] = match
    return elem


def _file_upload_element(field: FileUpload) -> dict[str, Any]:
    elem: dict[str, Any] = {
        "type": "file_input",
        "action_id": field.name,
    }
    if field.accept:
        elem["filetypes"] = [a.lstrip(".") for a in field.accept]
    if field.max_count and field.multiple:
        elem["max_files"] = field.max_count
    if not field.multiple:
        elem["max_files"] = 1
    return elem


# ─── Helpers ────────────────────────────────────────────────────────────


def _option(value: str, label: str) -> dict[str, Any]:
    return {
        "value": value,
        "text": {"type": "plain_text", "text": _truncate(label, 75)},
    }


def _truncate(s: str, max_len: int) -> str:
    return s if len(s) <= max_len else s[: max_len - 1] + "…"
