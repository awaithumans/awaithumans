"""Date and time form field primitives.

- DatePicker: single date.
- DateTimePicker: date + time.
- DateRange: start date + end date.
- TimePicker: time of day.

All values travel on the wire as ISO 8601 strings (YYYY-MM-DD,
YYYY-MM-DDTHH:MM:SS, HH:MM:SS) to stay JSON-safe across languages.
"""

from __future__ import annotations

from typing import Literal

from awaithumans.forms.base import FormFieldBase

# ─── Classes ─────────────────────────────────────────────────────────────


class DatePicker(FormFieldBase):
    """Single calendar date. Value is ISO date string 'YYYY-MM-DD'."""

    kind: Literal["date"] = "date"
    min_date: str | None = None
    max_date: str | None = None
    default: str | None = None


class DateTimePicker(FormFieldBase):
    """Date + time. Value is ISO datetime string 'YYYY-MM-DDTHH:MM:SS[Z|±HH:MM]'."""

    kind: Literal["datetime"] = "datetime"
    min_datetime: str | None = None
    max_datetime: str | None = None
    timezone: str | None = None
    default: str | None = None


class DateRange(FormFieldBase):
    """Start + end date. Value is {start, end} object with ISO date strings."""

    kind: Literal["date_range"] = "date_range"
    min_date: str | None = None
    max_date: str | None = None
    min_days: int | None = None
    max_days: int | None = None


class TimePicker(FormFieldBase):
    """Time of day. Value is ISO time string 'HH:MM[:SS]'."""

    kind: Literal["time"] = "time"
    min_time: str | None = None
    max_time: str | None = None
    step_minutes: int = 15
    default: str | None = None


# ─── DSL helpers ─────────────────────────────────────────────────────────


def date_picker(
    *,
    label: str | None = None,
    hint: str | None = None,
    min_date: str | None = None,
    max_date: str | None = None,
    default: str | None = None,
) -> DatePicker:
    return DatePicker(
        label=label,
        hint=hint,
        min_date=min_date,
        max_date=max_date,
        default=default,
    )


def datetime_picker(
    *,
    label: str | None = None,
    hint: str | None = None,
    min_datetime: str | None = None,
    max_datetime: str | None = None,
    timezone: str | None = None,
    default: str | None = None,
) -> DateTimePicker:
    return DateTimePicker(
        label=label,
        hint=hint,
        min_datetime=min_datetime,
        max_datetime=max_datetime,
        timezone=timezone,
        default=default,
    )


def date_range(
    *,
    label: str | None = None,
    hint: str | None = None,
    min_date: str | None = None,
    max_date: str | None = None,
    min_days: int | None = None,
    max_days: int | None = None,
) -> DateRange:
    return DateRange(
        label=label,
        hint=hint,
        min_date=min_date,
        max_date=max_date,
        min_days=min_days,
        max_days=max_days,
    )


def time_picker(
    *,
    label: str | None = None,
    hint: str | None = None,
    min_time: str | None = None,
    max_time: str | None = None,
    step_minutes: int = 15,
    default: str | None = None,
) -> TimePicker:
    return TimePicker(
        label=label,
        hint=hint,
        min_time=min_time,
        max_time=max_time,
        step_minutes=step_minutes,
        default=default,
    )
