"""Outbound webhook dispatch — sign / verify / fire.

Pins three things that the durable adapters (Temporal, LangGraph)
ride on:
  - The signature is HMAC-SHA256 over the EXACT body bytes the
    receiver gets, formatted as `sha256=<hex>`.
  - Receivers can verify with `verify_signature(body, header)` and
    constant-time-compare protects against timing attacks. Both the
    `sha256=` prefix and bare hex are accepted.
  - `fire_completion_webhook(task)` is a no-op on tasks without a
    callback_url (the dominant case — most tasks are long-poll only).
"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import AsyncGenerator, Iterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from awaithumans.server.core import encryption
from awaithumans.server.core.config import settings
from awaithumans.server.db.models import (  # noqa: F401 — register models
    AuditEntry,
    ConsumedEmailToken,
    EmailSenderIdentity,
    SlackInstallation,
    Task,
    TaskStatus,
    User,
)
from awaithumans.server.services.task_service import complete_task, create_task
from awaithumans.server.services.webhook_dispatch import (
    fire_completion_webhook,
    sign_body,
    verify_signature,
)


@pytest.fixture(autouse=True)
def _payload_key() -> Iterator[None]:
    """HKDF derives the webhook key from PAYLOAD_KEY — required."""
    original = settings.PAYLOAD_KEY
    settings.PAYLOAD_KEY = secrets.token_urlsafe(32)
    encryption.reset_key_cache()
    yield
    settings.PAYLOAD_KEY = original
    encryption.reset_key_cache()


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


# ─── sign / verify ────────────────────────────────────────────────────


def test_sign_body_returns_sha256_prefixed_hex() -> None:
    sig = sign_body(b'{"task_id":"abc"}')
    assert sig.startswith("sha256=")
    # HMAC-SHA256 → 64 hex chars
    assert len(sig) == len("sha256=") + 64


def test_verify_signature_accepts_correct_signature() -> None:
    body = b'{"hello":"world"}'
    sig = sign_body(body)
    assert verify_signature(body=body, signature=sig) is True


def test_verify_signature_accepts_bare_hex_without_prefix() -> None:
    """Some routing layers strip header prefixes; tolerate that."""
    body = b'{"hello":"world"}'
    full = sign_body(body)
    bare = full.removeprefix("sha256=")
    assert verify_signature(body=body, signature=bare) is True


def test_verify_signature_rejects_wrong_signature() -> None:
    body = b'{"hello":"world"}'
    assert verify_signature(body=body, signature="sha256=" + "0" * 64) is False


def test_verify_signature_rejects_missing_header() -> None:
    assert verify_signature(body=b"x", signature=None) is False
    assert verify_signature(body=b"x", signature="") is False


def test_verify_signature_body_change_invalidates() -> None:
    """Catches body-tamper. The HMAC is over the EXACT bytes the
    receiver gets — any modification flips the signature."""
    sig = sign_body(b'{"task_id":"abc"}')
    assert verify_signature(body=b'{"task_id":"abd"}', signature=sig) is False


# ─── fire_completion_webhook ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_fire_webhook_is_noop_when_callback_url_missing(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dominant case — most tasks long-poll, no webhook to fire.
    `fire_completion_webhook` must short-circuit before any HTTP call
    so the dispatch service can be invoked unconditionally on every
    terminal transition."""
    called = {"n": 0}

    class _BoomTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> Any:
            called["n"] += 1
            raise AssertionError("HTTP call attempted on no-callback task")

    monkeypatch.setattr(
        "awaithumans.server.services.webhook_dispatch.httpx.AsyncClient",
        lambda **_kw: httpx.AsyncClient(transport=_BoomTransport()),
    )

    task = await create_task(
        session,
        task="x",
        payload={},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="no-cb",
    )
    await fire_completion_webhook(task)
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_fire_webhook_posts_signed_body_when_callback_url_set(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: the receiver should be able to verify the
    incoming body against the X-Awaithumans-Signature header using
    the same HKDF-derived key."""
    received: dict[str, Any] = {}

    async def fake_handler(request: httpx.Request) -> httpx.Response:
        received["body"] = request.content
        received["headers"] = dict(request.headers)
        return httpx.Response(200, json={"ok": True})

    mock_transport = httpx.MockTransport(fake_handler)
    real_client = httpx.AsyncClient

    def _factory(**kw: Any) -> httpx.AsyncClient:
        # Drop any caller-supplied transport so MockTransport wins —
        # the dispatch service passes timeout=, not transport=. Bind
        # the original class to avoid recursing through the patch.
        kw.pop("transport", None)
        return real_client(transport=mock_transport, **kw)

    monkeypatch.setattr(
        "awaithumans.server.services.webhook_dispatch.httpx.AsyncClient", _factory
    )

    task = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="webhook-test",
        callback_url="https://example.test/callback",
    )
    # Mark complete so the body has the terminal status the receiver
    # would actually see.
    completed = await complete_task(
        session, task_id=task.id, response={"approved": True}
    )

    await fire_completion_webhook(completed)

    body = received["body"]
    sig = received["headers"]["x-awaithumans-signature"]
    assert verify_signature(body=body, signature=sig) is True
    payload = json.loads(body)
    assert payload["task_id"] == completed.id
    assert payload["status"] == "completed"
    assert payload["response"] == {"approved": True}


@pytest.mark.asyncio
async def test_fire_webhook_swallows_network_errors(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A flaky / refused receiver must NOT raise back into the
    caller's BackgroundTask. The agent's long-poll is the canonical
    way to learn about completion; webhook delivery is a best-effort
    optimisation."""

    async def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    boom_transport = httpx.MockTransport(boom)
    real_client = httpx.AsyncClient

    def _factory(**kw: Any) -> httpx.AsyncClient:
        kw.pop("transport", None)
        return real_client(transport=boom_transport, **kw)

    monkeypatch.setattr(
        "awaithumans.server.services.webhook_dispatch.httpx.AsyncClient", _factory
    )

    task = await create_task(
        session,
        task="x",
        payload={},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="boom",
        callback_url="https://offline.example.test/cb",
    )
    # Should not raise.
    await asyncio.wait_for(fire_completion_webhook(task), timeout=2)
