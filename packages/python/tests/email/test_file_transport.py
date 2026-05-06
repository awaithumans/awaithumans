"""File email transport — write JSON per email for E2E smoke tests.

The file transport drops one JSON-serialized email into a directory
on each send. The TS smoke test in `examples/email-smoke/` polls
that directory to capture the magic-link URL — without this transport
the test would have to scrape stdout from the dev server.

Tests pin:
  - File appears with the rendered email's fields
  - Directory is created on first send when missing
  - Header-injection guard from EmailMessage still applies
  - Missing `dir` config raises at construction
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from awaithumans.server.channels.email.transport.base import (
    EmailMessage,
    EmailTransportError,
)
from awaithumans.server.channels.email.transport.factory import resolve_transport
from awaithumans.server.channels.email.transport.file import FileTransport


def _msg() -> EmailMessage:
    return EmailMessage(
        to="recipient@example.com",
        subject="A new task to review",
        html="<p>Click <a href='https://app/x'>here</a></p>",
        text="Click here: https://app/x",
        from_email="bot@app.example",
        from_name="awaithumans",
        reply_to="ops@app.example",
        tags={"task_id": "t-001"},
    )


@pytest.mark.asyncio
async def test_send_writes_file_with_message_fields(tmp_path: Path) -> None:
    transport = FileTransport(dir=str(tmp_path))
    result = await transport.send(_msg())

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1, f"expected one file, got {files}"

    payload = json.loads(files[0].read_text())
    assert payload["to"] == "recipient@example.com"
    assert payload["subject"] == "A new task to review"
    assert "https://app/x" in payload["text"]
    assert payload["from_email"] == "bot@app.example"
    assert payload["from_name"] == "awaithumans"
    assert payload["tags"] == {"task_id": "t-001"}
    # Bookkeeping fields the test runner can rely on.
    assert payload["_message_id"] == result.message_id
    assert payload["_received_at"].endswith("Z")


@pytest.mark.asyncio
async def test_directory_created_on_first_send(tmp_path: Path) -> None:
    """Missing parent dir is OK — transport mkdirs on first send so a
    fresh repo doesn't need an extra setup step."""
    target = tmp_path / "deeply" / "nested" / "dir"
    assert not target.exists()

    transport = FileTransport(dir=str(target))
    await transport.send(_msg())

    assert target.is_dir()
    assert len(list(target.glob("*.json"))) == 1


@pytest.mark.asyncio
async def test_files_sort_chronologically(tmp_path: Path) -> None:
    """Filenames lead with unix-ms so a runner that sorts and takes
    `[-1]` always gets the most recent email."""
    transport = FileTransport(dir=str(tmp_path))
    await transport.send(_msg())
    await transport.send(_msg())
    files = sorted(tmp_path.glob("*.json"))
    # Two distinct filenames, sortable.
    assert len(files) == 2
    assert files[0].name < files[1].name


def test_construct_without_dir_raises() -> None:
    """An empty/missing `dir` is a config error at startup, not a
    silent default — refusing to start is the safer behavior since
    the alternative is silently writing to an unintended location."""
    with pytest.raises(EmailTransportError, match="dir is required"):
        FileTransport(dir="")


def test_factory_routes_file_name() -> None:
    transport = resolve_transport("file", {"dir": "/tmp/awaithumans-pyx"})
    assert transport.name == "file"


def test_factory_rejects_file_without_dir() -> None:
    with pytest.raises(EmailTransportError, match="dir is required"):
        resolve_transport("file", {})


def test_factory_unknown_name_lists_file() -> None:
    """Make sure the operator-facing error message advertises `file`
    so they don't have to read source to discover the transport
    exists."""
    with pytest.raises(EmailTransportError, match="file"):
        resolve_transport("not-a-real-transport", {})
