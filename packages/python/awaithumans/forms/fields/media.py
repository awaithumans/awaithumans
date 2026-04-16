"""Media form field primitives.

Input:
- FileUpload: upload one or more files.
- Signature: draw a signature (dashboard-only native; link-out elsewhere).

Display (read-only context for the human, not inputs):
- Image: embed an image.
- Video: embed a video.
- PdfViewer: embed a PDF.
- HtmlBlock: embed raw HTML (developer-trusted).
"""

from __future__ import annotations

from typing import Literal

from awaithumans.forms.base import FormFieldBase

# ─── Input classes ───────────────────────────────────────────────────────


class FileUpload(FormFieldBase):
    """Upload one or more files. Value is list of uploaded-file descriptors."""

    kind: Literal["file_upload"] = "file_upload"
    accept: list[str] | None = None
    max_size_bytes: int | None = None
    multiple: bool = False
    min_count: int | None = None
    max_count: int | None = None


class Signature(FormFieldBase):
    """Signature capture. Value is a base64 PNG or SVG string.

    Dashboard renders as a canvas. Slack/email degrade to link-out.
    """

    kind: Literal["signature"] = "signature"
    format: Literal["png", "svg"] = "png"


# ─── Display classes ─────────────────────────────────────────────────────


class Image(FormFieldBase):
    """Read-only image. Not an input."""

    kind: Literal["image"] = "image"
    url: str
    alt: str | None = None
    width: int | None = None
    height: int | None = None
    required: bool = False


class Video(FormFieldBase):
    """Read-only video. Not an input."""

    kind: Literal["video"] = "video"
    url: str
    poster_url: str | None = None
    autoplay: bool = False
    required: bool = False


class PdfViewer(FormFieldBase):
    """Embedded PDF viewer. Not an input."""

    kind: Literal["pdf_viewer"] = "pdf_viewer"
    url: str
    height: int | None = None
    required: bool = False


class HtmlBlock(FormFieldBase):
    """Raw HTML block. Developer-trusted; server-side renderers sanitize when needed.

    Use only for HTML authored by the developer, not user-supplied content.
    """

    kind: Literal["html"] = "html"
    html: str
    required: bool = False


# ─── DSL helpers ─────────────────────────────────────────────────────────


def file_upload(
    *,
    label: str | None = None,
    hint: str | None = None,
    accept: list[str] | None = None,
    max_size_bytes: int | None = None,
    multiple: bool = False,
    min_count: int | None = None,
    max_count: int | None = None,
) -> FileUpload:
    return FileUpload(
        label=label,
        hint=hint,
        accept=accept,
        max_size_bytes=max_size_bytes,
        multiple=multiple,
        min_count=min_count,
        max_count=max_count,
    )


def signature(
    *,
    label: str | None = None,
    hint: str | None = None,
    format: Literal["png", "svg"] = "png",
) -> Signature:
    return Signature(label=label, hint=hint, format=format)


def image(
    url: str,
    *,
    label: str | None = None,
    alt: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> Image:
    return Image(url=url, label=label, alt=alt, width=width, height=height)


def video(
    url: str,
    *,
    label: str | None = None,
    poster_url: str | None = None,
    autoplay: bool = False,
) -> Video:
    return Video(url=url, label=label, poster_url=poster_url, autoplay=autoplay)


def pdf_viewer(
    url: str,
    *,
    label: str | None = None,
    height: int | None = None,
) -> PdfViewer:
    return PdfViewer(url=url, label=label, height=height)


def html(raw: str, *, label: str | None = None) -> HtmlBlock:
    return HtmlBlock(html=raw, label=label)
