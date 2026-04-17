"""Selection form field primitives.

- Switch: yes/no (boolean).
- SingleSelect: pick one (renders as radio, dropdown, or buttons depending on option count).
- MultiSelect: pick many (renders as checkboxes or multi-select).
- PictureChoice: pick one/many with an image per option.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from awaithumans.forms.base import FormFieldBase

# ─── Supporting types ────────────────────────────────────────────────────


class SelectOption(BaseModel):
    """One option in a select/multi-select/ranking field."""

    value: str
    label: str
    hint: str | None = None


class PictureOption(BaseModel):
    """One option in a picture-choice field."""

    value: str
    label: str
    image_url: str
    hint: str | None = None


# ─── Classes ─────────────────────────────────────────────────────────────


class Switch(FormFieldBase):
    """Boolean yes/no toggle."""

    kind: Literal["switch"] = "switch"
    true_label: str = "Yes"
    false_label: str = "No"
    default: bool | None = None


class SingleSelect(FormFieldBase):
    """Pick exactly one option."""

    kind: Literal["single_select"] = "single_select"
    options: list[SelectOption]
    default: str | None = None


class MultiSelect(FormFieldBase):
    """Pick zero or more options."""

    kind: Literal["multi_select"] = "multi_select"
    options: list[SelectOption]
    default: list[str] = Field(default_factory=list)
    min_count: int | None = None
    max_count: int | None = None


class PictureChoice(FormFieldBase):
    """Pick one or many, with an image per option."""

    kind: Literal["picture_choice"] = "picture_choice"
    options: list[PictureOption]
    multiple: bool = False
    default: list[str] = Field(default_factory=list)


# ─── DSL helpers ─────────────────────────────────────────────────────────


def switch(
    *,
    label: str | None = None,
    hint: str | None = None,
    true_label: str = "Yes",
    false_label: str = "No",
    default: bool | None = None,
) -> Switch:
    return Switch(
        label=label,
        hint=hint,
        true_label=true_label,
        false_label=false_label,
        default=default,
    )


def single_select(
    *,
    options: list[SelectOption | tuple[str, str] | str],
    label: str | None = None,
    hint: str | None = None,
    default: str | None = None,
) -> SingleSelect:
    return SingleSelect(
        label=label,
        hint=hint,
        options=_normalize_options(options),
        default=default,
    )


def multi_select(
    *,
    options: list[SelectOption | tuple[str, str] | str],
    label: str | None = None,
    hint: str | None = None,
    default: list[str] | None = None,
    min_count: int | None = None,
    max_count: int | None = None,
) -> MultiSelect:
    return MultiSelect(
        label=label,
        hint=hint,
        options=_normalize_options(options),
        default=default or [],
        min_count=min_count,
        max_count=max_count,
    )


def picture_choice(
    *,
    options: list[PictureOption | dict[str, str]],
    label: str | None = None,
    hint: str | None = None,
    multiple: bool = False,
    default: list[str] | None = None,
) -> PictureChoice:
    normalized: list[PictureOption] = []
    for opt in options:
        if isinstance(opt, PictureOption):
            normalized.append(opt)
        else:
            normalized.append(PictureOption(**opt))
    return PictureChoice(
        label=label,
        hint=hint,
        options=normalized,
        multiple=multiple,
        default=default or [],
    )


# ─── Helpers ─────────────────────────────────────────────────────────────


def _normalize_options(
    raw: list[SelectOption | tuple[str, str] | str],
) -> list[SelectOption]:
    """Accept SelectOption, (value, label) tuples, or bare strings (value=label)."""
    out: list[SelectOption] = []
    for item in raw:
        if isinstance(item, SelectOption):
            out.append(item)
        elif isinstance(item, tuple):
            out.append(SelectOption(value=item[0], label=item[1]))
        elif isinstance(item, str):
            out.append(SelectOption(value=item, label=item))
        else:
            raise TypeError(
                "Options must be SelectOption, (value, label) tuple, or str. "
                f"Got: {type(item).__name__}"
            )
    return out
