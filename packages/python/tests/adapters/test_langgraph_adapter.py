"""LangGraph adapter — interrupt/resume contract + driver loop.

Three test surfaces:

  1. **Node-side `await_human`** raises `GraphInterrupt` with the
     awaithumans descriptor on first call, returns the validated
     response on second call (when the driver passed
     `Command(resume=...)`). Verified by stubbing `interrupt(...)`.

  2. **Descriptor extraction** — the driver pattern-matches on the
     `awaithumans` key. Other interrupts (operator confirmations,
     branching decisions) must NOT be consumed.

  3. **Driver poll loop** — `_wait_for_human` POSTs the task,
     long-polls until terminal, raises typed errors on
     timed_out/cancelled/exhausted. Tested with httpx.MockTransport.

End-to-end (real graph + real interrupt) is out of scope for unit
tests because `langgraph.graph.StateGraph` boots a checkpointer +
runtime; the descriptor-shape contract here is the cross-language
parity guarantee that matters."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from awaithumans.adapters.langgraph import (
    _default_idempotency_key,
    _extract_descriptor,
    _INTERRUPT_KEY,
    _serialize_assign_to,
    _wait_for_human,
    await_human,
)
from awaithumans.errors import (
    SchemaValidationError,
    TaskCancelledError,
    TaskTimeoutError,
    VerificationExhaustedError,
)


class _Payload(BaseModel):
    amount: int


class _Decision(BaseModel):
    approved: bool


# ─── Node-side: await_human ─────────────────────────────────────────


def test_await_human_calls_interrupt_with_awaithumans_descriptor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First call: `interrupt(...)` raises (the LangGraph runtime
    catches it). We assert it was passed our descriptor shape so the
    driver can pattern-match."""
    seen: dict[str, Any] = {}

    def fake_interrupt(value: Any) -> Any:
        seen["value"] = value
        # Simulate the resume-side behavior: return the response dict
        # the driver will pass back via Command(resume=...).
        return {"approved": True}

    import langgraph.types

    monkeypatch.setattr(langgraph.types, "interrupt", fake_interrupt)

    result = await_human(
        task="Approve refund?",
        payload_schema=_Payload,
        payload=_Payload(amount=100),
        response_schema=_Decision,
        timeout_seconds=900,
    )

    # Validated typed response is returned on resume.
    assert result == _Decision(approved=True)
    # Descriptor shape — driver depends on this exact wire format.
    desc = seen["value"]
    assert _INTERRUPT_KEY in desc
    body = desc[_INTERRUPT_KEY]
    assert body["task"] == "Approve refund?"
    assert body["payload"] == {"amount": 100}
    assert body["timeout_seconds"] == 900
    assert body["idempotency_key"].startswith("langgraph:")
    assert "payload_schema" in body and "response_schema" in body


def test_await_human_validates_response_schema_on_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the driver resumes with garbage that doesn't match
    response_schema, raise SchemaValidationError. Mirrors direct-
    mode SDK contract — typed catch in user code."""
    import langgraph.types

    monkeypatch.setattr(langgraph.types, "interrupt", lambda _v: {"wrong_field": 1})

    with pytest.raises(SchemaValidationError):
        await_human(
            task="x",
            payload_schema=_Payload,
            payload=_Payload(amount=1),
            response_schema=_Decision,
            timeout_seconds=900,
        )


def test_default_idempotency_key_is_deterministic_and_prefixed() -> None:
    """Same (task, payload) → same key on every call, so re-running
    a node hits the server's dedup gate. Prefix lets operators
    filter awaithumans tasks across multi-source servers."""
    a = _default_idempotency_key("Approve", _Payload(amount=100))
    b = _default_idempotency_key("Approve", _Payload(amount=100))
    c = _default_idempotency_key("Approve", _Payload(amount=200))
    assert a == b
    assert a != c
    assert a.startswith("langgraph:")


def test_serialize_assign_to_handles_email_string() -> None:
    assert _serialize_assign_to("ops@acme.com") == {"email": "ops@acme.com"}
    assert _serialize_assign_to(["a@b.com", "c@d.com"]) == {
        "emails": ["a@b.com", "c@d.com"]
    }
    assert _serialize_assign_to(None) is None


# ─── Descriptor extraction ──────────────────────────────────────────


def test_extract_descriptor_finds_awaithumans_key_in_dict() -> None:
    payload = {_INTERRUPT_KEY: {"task": "x", "payload": {}}}
    assert _extract_descriptor(payload) == {"task": "x", "payload": {}}


def test_extract_descriptor_walks_list_of_interrupt_objects() -> None:
    """LangGraph state.interrupts is a list of Interrupt objects;
    the dict lives at `.value`. Tolerate both shapes."""

    class _FakeInterrupt:
        def __init__(self, value: Any) -> None:
            self.value = value

    payload = [_FakeInterrupt({_INTERRUPT_KEY: {"task": "x"}})]
    assert _extract_descriptor(payload) == {"task": "x"}


def test_extract_descriptor_ignores_non_awaithumans_interrupts() -> None:
    """An operator-confirmation interrupt with a different key must
    return None — the driver won't consume it, the user's own logic
    handles it."""
    assert _extract_descriptor({"operator_confirm": {"prompt": "ok?"}}) is None
    assert _extract_descriptor("plain string") is None
    assert _extract_descriptor(None) is None


# ─── Driver: HTTP create + long-poll ────────────────────────────────


@pytest.fixture
def mock_httpx(monkeypatch: pytest.MonkeyPatch):
    """Helper: install a httpx.MockTransport-driven AsyncClient
    factory on the langgraph adapter so we can script the
    create-task + poll round-trip."""
    real_client = httpx.AsyncClient

    def install(handler):
        transport = httpx.MockTransport(handler)

        def _factory(**kw: Any) -> httpx.AsyncClient:
            kw.pop("transport", None)
            return real_client(transport=transport, **kw)

        monkeypatch.setattr(
            "awaithumans.adapters.langgraph.httpx.AsyncClient", _factory
        )

    return install


def _descriptor() -> dict[str, Any]:
    """Fixture-ish: build the descriptor a node would have produced."""
    return {
        "task": "Approve refund?",
        "payload": {"amount": 100},
        "payload_schema": {},
        "response_schema": {},
        "timeout_seconds": 900,
        "idempotency_key": "langgraph:abc123",
        "assign_to": None,
        "notify": None,
        "verifier_config": None,
        "redact_payload": False,
    }


@pytest.mark.asyncio
async def test_wait_for_human_returns_response_on_completed(mock_httpx) -> None:
    sent_body: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tasks":
            sent_body.update(json.loads(request.content))
            return httpx.Response(201, json={"id": "task-1"})
        if request.url.path.endswith("/poll"):
            return httpx.Response(
                200,
                json={"status": "completed", "response": {"approved": True}},
            )
        return httpx.Response(404)

    mock_httpx(handler)

    result = await _wait_for_human(
        _descriptor(),
        server_url="http://test",
        api_key="test-bearer",
        poll_interval_seconds=1,
    )
    assert result == {"approved": True}
    # POST body shape — must be exactly what the awaithumans server
    # accepts (matches CreateTaskRequest schema).
    assert sent_body["idempotency_key"] == "langgraph:abc123"
    assert sent_body["timeout_seconds"] == 900


@pytest.mark.asyncio
async def test_wait_for_human_raises_typed_errors_on_terminal_statuses(
    mock_httpx,
) -> None:
    """Each terminal status maps to a typed exception. User catches
    these in `drive_human_loop`'s callsite to recover (e.g., assign
    to a different reviewer on cancellation)."""
    statuses = [
        ("cancelled", TaskCancelledError),
        ("timed_out", TaskTimeoutError),
        ("verification_exhausted", VerificationExhaustedError),
    ]
    for status, exc in statuses:

        async def handler(
            request: httpx.Request, _s: str = status
        ) -> httpx.Response:
            if request.url.path == "/api/tasks":
                return httpx.Response(201, json={"id": "task-1"})
            return httpx.Response(
                200, json={"status": _s, "response": None, "verification_attempt": 3}
            )

        mock_httpx(handler)
        with pytest.raises(exc):
            await _wait_for_human(
                _descriptor(),
                server_url="http://test",
                api_key=None,
                poll_interval_seconds=1,
            )


@pytest.mark.asyncio
async def test_wait_for_human_raises_on_5xx_create_failure(mock_httpx) -> None:
    """Server rejected the create — fail loud rather than silent."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    mock_httpx(handler)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        await _wait_for_human(
            _descriptor(),
            server_url="http://test",
            api_key=None,
            poll_interval_seconds=1,
        )
