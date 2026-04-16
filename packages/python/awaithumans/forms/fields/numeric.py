"""Numeric form field primitives.

- Slider: bounded numeric range with step.
- StarRating: 1..N stars.
- OpinionScale: labeled N-point scale (e.g. 1..10 with "strongly disagree"/"strongly agree").
- Ranking: order a list of items.

Bare numeric inputs (amounts, counts) live in text.py as
ShortText with subtype="number" or subtype="currency".
"""

from __future__ import annotations

from typing import Literal

from awaithumans.forms.base import FormFieldBase
from awaithumans.forms.fields.selection import SelectOption, _normalize_options

# ─── Classes ─────────────────────────────────────────────────────────────


class Slider(FormFieldBase):
    """Numeric slider with min/max/step."""

    kind: Literal["slider"] = "slider"
    min: float = 0
    max: float = 100
    step: float = 1
    default: float | None = None
    prefix: str | None = None
    suffix: str | None = None


class StarRating(FormFieldBase):
    """1..max star rating."""

    kind: Literal["star_rating"] = "star_rating"
    max: int = 5
    default: int | None = None


class OpinionScale(FormFieldBase):
    """Labeled N-point scale (e.g. 1..10 NPS)."""

    kind: Literal["opinion_scale"] = "opinion_scale"
    min: int = 1
    max: int = 10
    min_label: str | None = None
    max_label: str | None = None
    default: int | None = None


class Ranking(FormFieldBase):
    """Rank a list of items (drag-drop in dashboard; link-out elsewhere)."""

    kind: Literal["ranking"] = "ranking"
    options: list[SelectOption]


# ─── DSL helpers ─────────────────────────────────────────────────────────


def slider(
    *,
    min: float = 0,
    max: float = 100,
    step: float = 1,
    label: str | None = None,
    hint: str | None = None,
    default: float | None = None,
    prefix: str | None = None,
    suffix: str | None = None,
) -> Slider:
    return Slider(
        label=label,
        hint=hint,
        min=min,
        max=max,
        step=step,
        default=default,
        prefix=prefix,
        suffix=suffix,
    )


def star_rating(
    *,
    max: int = 5,
    label: str | None = None,
    hint: str | None = None,
    default: int | None = None,
) -> StarRating:
    return StarRating(label=label, hint=hint, max=max, default=default)


def opinion_scale(
    *,
    min: int = 1,
    max: int = 10,
    label: str | None = None,
    hint: str | None = None,
    min_label: str | None = None,
    max_label: str | None = None,
    default: int | None = None,
) -> OpinionScale:
    return OpinionScale(
        label=label,
        hint=hint,
        min=min,
        max=max,
        min_label=min_label,
        max_label=max_label,
        default=default,
    )


def ranking(
    *,
    options: list[SelectOption | tuple[str, str] | str],
    label: str | None = None,
    hint: str | None = None,
) -> Ranking:
    return Ranking(
        label=label,
        hint=hint,
        options=_normalize_options(options),
    )
