"""Layout form field primitives.

- Section: visual heading with optional subtitle. Flat — subsequent fields
  belong to it until the next Section.
- Divider: horizontal rule.
- SectionCollapse: collapsible group containing nested fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field

from awaithumans.forms.base import FormFieldBase

if TYPE_CHECKING:
    from awaithumans.forms.definition import FormField

# ─── Classes ─────────────────────────────────────────────────────────────


class Section(FormFieldBase):
    """Visual heading — not an input.

    All fields listed after a Section belong to that section until the next
    Section or the end of the form.
    """

    kind: Literal["section"] = "section"
    title: str
    subtitle: str | None = None
    required: bool = False


class Divider(FormFieldBase):
    """Horizontal rule separator."""

    kind: Literal["divider"] = "divider"
    required: bool = False


class SectionCollapse(FormFieldBase):
    """Collapsible group with nested fields inside."""

    kind: Literal["section_collapse"] = "section_collapse"
    title: str
    subtitle: str | None = None
    fields: list[FormField] = Field(default_factory=list)
    default_open: bool = True
    required: bool = False


# ─── DSL helpers ─────────────────────────────────────────────────────────


def section(title: str, *, subtitle: str | None = None) -> Section:
    return Section(title=title, subtitle=subtitle)


def divider() -> Divider:
    return Divider()


def section_collapse(
    title: str,
    *,
    fields: list[FormField],
    subtitle: str | None = None,
    default_open: bool = True,
) -> SectionCollapse:
    return SectionCollapse(
        title=title,
        subtitle=subtitle,
        fields=fields,
        default_open=default_open,
    )
