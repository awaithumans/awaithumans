"""Form primitives for awaithumans.

Define a Pydantic response schema with form primitives attached via Annotated,
and the server will render it natively in the dashboard, Slack, and email.

    from typing import Annotated
    from pydantic import BaseModel
    from awaithumans.forms import switch, long_text, currency

    class WireApproval(BaseModel):
        approve: Annotated[bool, switch(label="Approve this wire?")]
        comment: Annotated[str | None, long_text(label="Reason")] = None

Public API — prefer importing from `awaithumans.forms` over per-module paths.
"""

from __future__ import annotations

from awaithumans.forms.base import FormFieldBase
from awaithumans.forms.capabilities import (
    CAPABILITIES,
    Channel,
    ChannelSupport,
    field_renders_in,
    form_renders_in,
    unsupported_fields,
)
from awaithumans.forms.definition import FORM_DEFINITION_VERSION, FormDefinition, FormField
from awaithumans.forms.extract import extract_form
from awaithumans.forms.fields.complex import Subform, Table, TableColumn, TableColumnKind
from awaithumans.forms.fields.date_time import (
    DatePicker,
    DateRange,
    DateTimePicker,
    TimePicker,
    date_picker,
    date_range,
    datetime_picker,
    time_picker,
)
from awaithumans.forms.fields.layout import (
    Divider,
    Section,
    SectionCollapse,
    divider,
    section,
    section_collapse,
)
from awaithumans.forms.fields.media import (
    FileUpload,
    HtmlBlock,
    Image,
    PdfViewer,
    Signature,
    Video,
    file_upload,
    html,
    image,
    pdf_viewer,
    signature,
    video,
)
from awaithumans.forms.fields.numeric import (
    OpinionScale,
    Ranking,
    Slider,
    StarRating,
    opinion_scale,
    ranking,
    slider,
    star_rating,
)
from awaithumans.forms.fields.selection import (
    MultiSelect,
    PictureChoice,
    SelectOption,
    SingleSelect,
    Switch,
    multi_select,
    picture_choice,
    single_select,
    switch,
)
from awaithumans.forms.fields.text import (
    DisplayText,
    LongText,
    RichText,
    ShortText,
    ShortTextSubtype,
    currency,
    display_text,
    email,
    long_text,
    password,
    phone,
    rich_text,
    short_text,
    url,
)
from awaithumans.forms.infer import infer_field_from_type
from awaithumans.forms.fields.complex import subform, table

__all__ = [
    # Framework
    "FORM_DEFINITION_VERSION",
    "FormDefinition",
    "FormField",
    "FormFieldBase",
    "extract_form",
    "infer_field_from_type",
    # Capabilities
    "CAPABILITIES",
    "Channel",
    "ChannelSupport",
    "field_renders_in",
    "form_renders_in",
    "unsupported_fields",
    # Text classes
    "DisplayText",
    "LongText",
    "RichText",
    "ShortText",
    "ShortTextSubtype",
    # Text helpers
    "currency",
    "display_text",
    "email",
    "long_text",
    "password",
    "phone",
    "rich_text",
    "short_text",
    "url",
    # Selection classes
    "MultiSelect",
    "PictureChoice",
    "SelectOption",
    "SingleSelect",
    "Switch",
    # Selection helpers
    "multi_select",
    "picture_choice",
    "single_select",
    "switch",
    # Numeric classes
    "OpinionScale",
    "Ranking",
    "Slider",
    "StarRating",
    # Numeric helpers
    "opinion_scale",
    "ranking",
    "slider",
    "star_rating",
    # Date/time classes
    "DatePicker",
    "DateRange",
    "DateTimePicker",
    "TimePicker",
    # Date/time helpers
    "date_picker",
    "date_range",
    "datetime_picker",
    "time_picker",
    # Media classes
    "FileUpload",
    "HtmlBlock",
    "Image",
    "PdfViewer",
    "Signature",
    "Video",
    # Media helpers
    "file_upload",
    "html",
    "image",
    "pdf_viewer",
    "signature",
    "video",
    # Layout classes
    "Divider",
    "Section",
    "SectionCollapse",
    # Layout helpers
    "divider",
    "section",
    "section_collapse",
    # Complex classes
    "Subform",
    "Table",
    "TableColumn",
    "TableColumnKind",
    # Complex helpers
    "subform",
    "table",
]
