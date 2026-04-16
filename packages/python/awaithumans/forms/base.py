"""Base class for form field primitives.

Every form field inherits from FormFieldBase. Subclasses add a `kind`
literal discriminator and any kind-specific configuration.

Usage via Pydantic Annotated:

    from typing import Annotated
    from pydantic import BaseModel
    from awaithumans.forms import switch, long_text

    class WireApproval(BaseModel):
        approve: Annotated[bool, switch(label="Approve this wire?")]
        comment: Annotated[str | None, long_text(label="Reason")] = None

The `name` and `required` fields are filled in by extract_form() — the
developer doesn't set them manually.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FormFieldBase(BaseModel):
    """Shared shape of every form field primitive.

    - `name` is the Pydantic attribute name; filled by extract_form().
    - `kind` is the discriminator for the FormField union.
    - `label`, `hint` are user-visible copy.
    - `required` is inferred from the Pydantic field's Optional/default.
    """

    name: str = ""
    kind: str
    label: str | None = None
    hint: str | None = None
    required: bool = True

    model_config = ConfigDict(populate_by_name=True)
