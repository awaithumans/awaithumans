"""FormField discriminated union + FormDefinition wire type.

This module assembles all primitive classes into a single tagged union
keyed by `kind` and exposes the top-level FormDefinition used across the
wire (SDK → server → channel renderers → dashboard).

Forward references inside recursive primitives (Subform, SectionCollapse)
are resolved here via model_rebuild().
"""

from __future__ import annotations

from typing import Annotated, Union

from pydantic import BaseModel, Field

from awaithumans.forms.fields.complex import Subform, Table
from awaithumans.forms.fields.date_time import (
    DatePicker,
    DateRange,
    DateTimePicker,
    TimePicker,
)
from awaithumans.forms.fields.layout import Divider, Section, SectionCollapse
from awaithumans.forms.fields.media import (
    FileUpload,
    HtmlBlock,
    Image,
    PdfViewer,
    Signature,
    Video,
)
from awaithumans.forms.fields.numeric import OpinionScale, Ranking, Slider, StarRating
from awaithumans.forms.fields.selection import (
    MultiSelect,
    PictureChoice,
    SingleSelect,
    Switch,
)
from awaithumans.forms.fields.text import DisplayText, LongText, RichText, ShortText

FORM_DEFINITION_VERSION = 1

FormField = Annotated[
    Union[
        # Text
        DisplayText,
        ShortText,
        LongText,
        RichText,
        # Selection
        Switch,
        SingleSelect,
        MultiSelect,
        PictureChoice,
        # Numeric
        Slider,
        StarRating,
        OpinionScale,
        Ranking,
        # Date/time
        DatePicker,
        DateTimePicker,
        DateRange,
        TimePicker,
        # Media
        FileUpload,
        Signature,
        Image,
        Video,
        PdfViewer,
        HtmlBlock,
        # Layout
        Section,
        Divider,
        SectionCollapse,
        # Complex
        Table,
        Subform,
    ],
    Field(discriminator="kind"),
]


class FormDefinition(BaseModel):
    """The full form — sent alongside a task, rendered per channel."""

    version: int = FORM_DEFINITION_VERSION
    fields: list[FormField]


# Resolve forward references inside recursive primitives.
_namespace = {"FormField": FormField}
SectionCollapse.model_rebuild(_types_namespace=_namespace)
Subform.model_rebuild(_types_namespace=_namespace)
FormDefinition.model_rebuild(_types_namespace=_namespace)
