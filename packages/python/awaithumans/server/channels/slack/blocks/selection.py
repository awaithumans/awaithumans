"""Selection element renderers: Switch, SingleSelect, MultiSelect, PictureChoice.

Picks between Block Kit element types based on option count for better UX:
  - single_select <= 4 options      → radio_buttons
  - single_select > 4 options       → static_select dropdown
  - multi_select <= 10 options      → checkboxes
  - multi_select > 10 options       → multi_static_select
  - picture_choice (any count)      → static_select / multi_static_select
      (Slack elements don't support images in options; the label still
      carries the meaning.)
"""

from __future__ import annotations

from typing import Any

from awaithumans.forms.fields.selection import (
    MultiSelect,
    PictureChoice,
    SingleSelect,
    Switch,
)
from awaithumans.server.channels.slack.blocks.helpers import option
from awaithumans.utils.constants import SLACK_SELECT_MAX_OPTIONS

# UX thresholds — swap to dropdown once the option list is too long
# to fit as individual radios/checkboxes without feeling cluttered.
_SINGLE_RADIO_THRESHOLD = 4
_MULTI_CHECKBOX_THRESHOLD = 10


def switch_element(field: Switch) -> dict[str, Any]:
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


def single_select_element(field: SingleSelect) -> dict[str, Any]:
    options = [option(o.value, o.label) for o in field.options[:SLACK_SELECT_MAX_OPTIONS]]
    if len(options) <= _SINGLE_RADIO_THRESHOLD:
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


def multi_select_element(field: MultiSelect) -> dict[str, Any]:
    options = [option(o.value, o.label) for o in field.options[:SLACK_SELECT_MAX_OPTIONS]]
    if len(options) <= _MULTI_CHECKBOX_THRESHOLD:
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


def picture_choice_element(field: PictureChoice) -> dict[str, Any]:
    options = [option(o.value, o.label) for o in field.options[:SLACK_SELECT_MAX_OPTIONS]]
    elem_type = "multi_static_select" if field.multiple else "static_select"
    return {
        "type": elem_type,
        "action_id": field.name,
        "options": options,
        "placeholder": {"type": "plain_text", "text": "Select…"},
    }
