"""Media element renderer: FileUpload.

Image primitives aren't inputs — they render as top-level `image` blocks
directly in the surfaces dispatcher.
"""

from __future__ import annotations

from typing import Any

from awaithumans.forms.fields.media import FileUpload


def file_upload_element(field: FileUpload) -> dict[str, Any]:
    elem: dict[str, Any] = {
        "type": "file_input",
        "action_id": field.name,
    }
    if field.accept:
        elem["filetypes"] = [a.lstrip(".") for a in field.accept]
    if field.max_count and field.multiple:
        elem["max_files"] = field.max_count
    if not field.multiple:
        elem["max_files"] = 1
    return elem
