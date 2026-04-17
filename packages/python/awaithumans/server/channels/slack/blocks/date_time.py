"""Date/time element renderers: DatePicker, DateTimePicker, TimePicker.

Slack's `datetimepicker` takes an epoch int for its initial value. We
don't plumb a default through for it — the form-level default is rarely
used and skipping it keeps the rendering trivially correct.
"""

from __future__ import annotations

from typing import Any

from awaithumans.forms.fields.date_time import (
    DatePicker,
    DateTimePicker,
    TimePicker,
)


def date_element(field: DatePicker) -> dict[str, Any]:
    elem: dict[str, Any] = {"type": "datepicker", "action_id": field.name}
    if field.default:
        elem["initial_date"] = field.default
    return elem


def datetime_element(field: DateTimePicker) -> dict[str, Any]:
    return {"type": "datetimepicker", "action_id": field.name}


def time_element(field: TimePicker) -> dict[str, Any]:
    elem: dict[str, Any] = {"type": "timepicker", "action_id": field.name}
    if field.default:
        elem["initial_time"] = field.default
    return elem
