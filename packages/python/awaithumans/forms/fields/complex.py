"""Complex form field primitives.

- Table: rows of typed cells. Homogeneous columns, variable row count.
  Cells support common types (text, number, switch, single_select, date);
  for rich nested fields use Subform.
- Subform: repeated group of arbitrary form fields.

Dashboard renders both natively. Slack/email degrade to link-out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from awaithumans.forms.base import FormFieldBase
from awaithumans.forms.fields.selection import SelectOption

if TYPE_CHECKING:
    from awaithumans.forms.definition import FormField


# ─── Table supporting type ───────────────────────────────────────────────


TableColumnKind = Literal[
    "short_text",
    "long_text",
    "number",
    "currency",
    "switch",
    "single_select",
    "date",
    "datetime",
]


class TableColumn(BaseModel):
    """One typed column in a Table."""

    name: str
    label: str
    kind: TableColumnKind = "short_text"
    required: bool = True
    placeholder: str | None = None
    options: list[SelectOption] | None = None
    currency_code: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    default: str | float | bool | None = None


# ─── Classes ─────────────────────────────────────────────────────────────


class Table(FormFieldBase):
    """Rows of typed cells. Value is list[dict] keyed by column name."""

    kind: Literal["table"] = "table"
    columns: list[TableColumn]
    min_rows: int | None = None
    max_rows: int | None = None
    initial_rows: int = 1
    allow_add_row: bool = True
    allow_remove_row: bool = True


class Subform(FormFieldBase):
    """Repeated group of form fields. Value is list[dict] keyed by field name."""

    kind: Literal["subform"] = "subform"
    fields: list["FormField"] = Field(default_factory=list)
    min_count: int | None = None
    max_count: int | None = None
    initial_count: int = 1
    add_label: str = "Add"
    remove_label: str = "Remove"


# ─── DSL helpers ─────────────────────────────────────────────────────────


def table(
    *,
    columns: list[TableColumn | dict[str, object]],
    label: str | None = None,
    hint: str | None = None,
    min_rows: int | None = None,
    max_rows: int | None = None,
    initial_rows: int = 1,
    allow_add_row: bool = True,
    allow_remove_row: bool = True,
) -> Table:
    normalized: list[TableColumn] = []
    for col in columns:
        if isinstance(col, TableColumn):
            normalized.append(col)
        else:
            normalized.append(TableColumn(**col))
    return Table(
        label=label,
        hint=hint,
        columns=normalized,
        min_rows=min_rows,
        max_rows=max_rows,
        initial_rows=initial_rows,
        allow_add_row=allow_add_row,
        allow_remove_row=allow_remove_row,
    )


def subform(
    *,
    fields: list["FormField"],
    label: str | None = None,
    hint: str | None = None,
    min_count: int | None = None,
    max_count: int | None = None,
    initial_count: int = 1,
    add_label: str = "Add",
    remove_label: str = "Remove",
) -> Subform:
    return Subform(
        label=label,
        hint=hint,
        fields=fields,
        min_count=min_count,
        max_count=max_count,
        initial_count=initial_count,
        add_label=add_label,
        remove_label=remove_label,
    )
