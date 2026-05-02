"""LangGraph adapter — interrupt/resume durable HITL.

Two halves, but unlike Temporal both run in the SAME process — the
LangGraph runtime is library-style, not a separate worker:

  1. **Inside a graph node** — call `await_human(...)`. We package
     the task descriptor and call LangGraph's `interrupt(...)`,
     which raises `GraphInterrupt` and parks the node. The graph's
     checkpointer persists the state; even if the host process dies,
     the next driver run resumes from this point.

  2. **In the driver loop** — call `drive_human_loop(graph, input,
     config, ...)`. The driver streams the graph, intercepts the
     awaithumans-shaped interrupt, POSTs the task to the awaithumans
     server, long-polls until terminal, and resumes the graph with
     `Command(resume=response)` until the graph completes.

LangGraph's signature pattern (vs Temporal's signal-based one) means
the graph itself doesn't talk HTTP. The driver does. That keeps node
code synchronous and trivial; durability comes from the
checkpointer, which the user already configured for any graph that
uses interrupts.

Wire diagram:

    driver                         awaithumans server          graph node
    ──────                         ──────────────────          ──────────
    graph.stream(input)
                                                              interrupt(...)
                                                              ↑ raised
    catch __interrupt__
    ── POST /api/tasks ──►         create task
                                   notify human (slack/email)
    ◄── task_id ──────────
    long-poll
                                   ── human completes ───
    ◄── response ─────────
    graph.stream(Command(resume=response), config)
                                                              interrupt returns
                                                              node continues

Cross-language: a LangGraph driver running in Python can use the
same task on the same awaithumans server that a TypeScript driver
would use — the wire format is identical.

Requires: `pip install "awaithumans[langgraph]"`. The whole module
is import-safe without langgraph installed; the call sites
fail-fast with a clear ImportError when actually invoked."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from awaithumans.errors import (
    SchemaValidationError,
    TaskCancelledError,
    TaskTimeoutError,
    VerificationExhaustedError,
)
from awaithumans.types import VerifierConfig
from awaithumans.utils.constants import POLL_INTERVAL_SECONDS

logger = logging.getLogger("awaithumans.adapters.langgraph")

T = TypeVar("T", bound=BaseModel)

# Magic key the driver pattern-matches on. Other interrupts in the
# graph (operator confirmations, branching decisions) won't have
# this key, so the driver can ignore them and let the calling code
# handle them however it wants.
_INTERRUPT_KEY = "awaithumans"


def _require_langgraph() -> None:
    """Lazy import gate — langgraph is an optional extra."""
    try:
        import langgraph  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "The LangGraph adapter requires the [langgraph] extra.\n"
            'Install with: pip install "awaithumans[langgraph]"'
        ) from exc


# ─── Node-side: await_human ──────────────────────────────────────────


def await_human(
    *,
    task: str,
    payload_schema: type[T],
    payload: BaseModel,
    response_schema: type[T],
    timeout_seconds: int,
    idempotency_key: str | None = None,
    assign_to: object | None = None,
    notify: list[str] | None = None,
    verifier: VerifierConfig | None = None,
    redact_payload: bool = False,
) -> T:
    """Suspend a LangGraph node until a human completes a task.

    The first execution of this call raises `GraphInterrupt`,
    surfacing the task descriptor to the driver loop. The driver
    creates the task on the awaithumans server, waits for the human,
    and resumes the graph with the response. On the second
    execution (after resume), this function returns the validated
    response — the rest of the node's code runs as if `interrupt`
    were a synchronous "block until human responds."

    Note: this is a SYNC function (matches LangGraph's node API
    surface). The driver loop is async; that's where the polling
    happens. Inside a node, `await_human` looks like a blocking
    call — exactly the developer-experience contract we want.

    Re-entry semantics: the LangGraph runtime re-executes the whole
    node on resume. If your node does work BEFORE `await_human`,
    that work runs twice (once before interrupt, once on resume).
    Treat the await_human call as a checkpoint; do side effects
    AFTER it, or wrap them in idempotency."""
    _require_langgraph()

    from langgraph.types import interrupt

    descriptor = {
        _INTERRUPT_KEY: {
            "task": task,
            "payload": payload.model_dump(mode="json"),
            "payload_schema": payload_schema.model_json_schema(),
            "response_schema": response_schema.model_json_schema(),
            "timeout_seconds": timeout_seconds,
            "idempotency_key": idempotency_key
            or _default_idempotency_key(task, payload),
            "assign_to": _serialize_assign_to(assign_to),
            "notify": notify,
            "verifier_config": verifier.model_dump() if verifier else None,
            "redact_payload": redact_payload,
        }
    }

    raw_response = interrupt(descriptor)

    # On resume, `raw_response` is whatever the driver passed in
    # `Command(resume=...)`. Validate against the user's
    # response_schema so they get a typed Pydantic instance back —
    # consistent with the direct-mode SDK.
    try:
        return response_schema.model_validate(raw_response)
    except Exception as exc:  # noqa: BLE001
        raise SchemaValidationError("response", str(exc)) from exc


def _default_idempotency_key(task: str, payload: BaseModel) -> str:
    """Deterministic key for a (task, payload) pair, prefixed for routing.

    The driver can rely on the `langgraph:` prefix when introspecting
    or filtering tasks across multiple sources sharing one
    awaithumans server."""
    canonical = json.dumps(
        {"task": task, "payload": payload.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"langgraph:{hashlib.sha256(canonical.encode()).hexdigest()[:32]}"


def _serialize_assign_to(assign_to: object | None) -> dict[str, Any] | None:
    if assign_to is None:
        return None
    if isinstance(assign_to, str):
        return {"email": assign_to}
    if isinstance(assign_to, list):
        return {"emails": assign_to}
    if isinstance(assign_to, BaseModel):
        return assign_to.model_dump(mode="json")
    return {"value": str(assign_to)}


# ─── Driver-side: drive_human_loop ──────────────────────────────────


async def drive_human_loop(
    graph: Any,
    input_state: Any,
    *,
    config: dict[str, Any],
    server_url: str,
    api_key: str | None = None,
    poll_interval_seconds: int = POLL_INTERVAL_SECONDS,
) -> Any:
    """Run a graph until it completes, handling awaithumans interrupts.

    Streams the compiled graph, intercepts interrupts whose payload
    has the awaithumans key, creates the task on the awaithumans
    server, long-polls until terminal, and resumes the graph with
    `Command(resume=response)`. Returns the graph's final state.

    Other interrupts (interrupts your graph raises for non-
    awaithumans reasons) re-raise — pass them up to the caller. The
    `_INTERRUPT_KEY` discriminator means we never accidentally consume
    an interrupt that wasn't ours.

    For long-running graphs the user can resume from a checkpoint:
    pass the same `config` (with `thread_id` set) on the next run
    and LangGraph picks up where it left off. The driver is
    stateless across calls.

    Polling-based by design — durability comes from LangGraph's
    checkpointer, not from us. A webhook-driven driver
    (`dispatch_resume`) for low-latency setups is a planned post-
    launch follow-up."""
    _require_langgraph()

    from langgraph.types import Command

    current_input: Any = input_state

    while True:
        descriptor = await _stream_until_interrupt(graph, current_input, config)
        if descriptor is None:
            # Graph completed without an awaithumans interrupt —
            # return the final state.
            state = await _aget_state(graph, config)
            return state

        response = await _wait_for_human(
            descriptor,
            server_url=server_url,
            api_key=api_key,
            poll_interval_seconds=poll_interval_seconds,
        )

        # Resume with the validated response. The node's
        # `interrupt(...)` call returns this value on the next
        # execution and proceeds.
        current_input = Command(resume=response)


async def _stream_until_interrupt(
    graph: Any, input_state: Any, config: dict[str, Any]
) -> dict[str, Any] | None:
    """Drive the graph forward until it either completes or hits an
    awaithumans-shaped interrupt.

    Returns the interrupt descriptor (the `awaithumans` sub-dict the
    node passed to `interrupt(...)`) or None if the graph completed."""
    # LangGraph's astream yields chunks per node update. Interrupts
    # surface either as a `__interrupt__` key on a chunk or via the
    # state machine — depending on the version. We handle both.
    async for chunk in graph.astream(input_state, config=config, stream_mode="updates"):
        if isinstance(chunk, dict) and "__interrupt__" in chunk:
            interrupt_payload = chunk["__interrupt__"]
            descriptor = _extract_descriptor(interrupt_payload)
            if descriptor is not None:
                return descriptor

    # Graph finished without yielding our interrupt key. Could be:
    #  - Normal completion
    #  - A non-awaithumans interrupt that the user's driver handles
    # Check the state for a pending interrupt that ISN'T ours.
    state = await _aget_state(graph, config)
    interrupts = getattr(state, "interrupts", None) or []
    for itr in interrupts:
        descriptor = _extract_descriptor(getattr(itr, "value", itr))
        if descriptor is not None:
            return descriptor

    return None


def _extract_descriptor(payload: Any) -> dict[str, Any] | None:
    """LangGraph's interrupt payload comes in two shapes depending on
    version: a bare dict, or a list of `Interrupt` objects (each with
    `.value`). Walk both to find the awaithumans dict."""
    if isinstance(payload, dict) and _INTERRUPT_KEY in payload:
        sub = payload[_INTERRUPT_KEY]
        return sub if isinstance(sub, dict) else None
    if isinstance(payload, list | tuple):
        for item in payload:
            value = getattr(item, "value", item)
            descriptor = _extract_descriptor(value)
            if descriptor is not None:
                return descriptor
    return None


async def _aget_state(graph: Any, config: dict[str, Any]) -> Any:
    """LangGraph's `get_state` is sync in some versions, async in
    others; tolerate both."""
    method = getattr(graph, "aget_state", None) or graph.get_state
    result = method(config)
    if asyncio.iscoroutine(result):
        return await result
    return result


# ─── HTTP: create task + long-poll ──────────────────────────────────


async def _wait_for_human(
    descriptor: dict[str, Any],
    *,
    server_url: str,
    api_key: str | None,
    poll_interval_seconds: int,
) -> Any:
    """Create the task on the awaithumans server, long-poll for
    completion, return the human's response (a dict — validated
    against the response schema by the node-side `await_human`).

    Raises `TaskTimeoutError`, `TaskCancelledError`,
    `VerificationExhaustedError` to match the direct-mode SDK
    contract; user catches these in the driver call site."""
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    base = server_url.rstrip("/")
    body = {
        "task": descriptor["task"],
        "payload": descriptor["payload"],
        "payload_schema": descriptor["payload_schema"],
        "response_schema": descriptor["response_schema"],
        "form_definition": None,
        "timeout_seconds": descriptor["timeout_seconds"],
        "idempotency_key": descriptor["idempotency_key"],
        "assign_to": descriptor.get("assign_to"),
        "notify": descriptor.get("notify"),
        "verifier_config": descriptor.get("verifier_config"),
        "redact_payload": descriptor.get("redact_payload", False),
        "callback_url": None,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{base}/api/tasks", json=body, headers=headers)
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"awaithumans server rejected task creation "
                f"(HTTP {resp.status_code}): {resp.text[:500]}"
            )
        task_id = resp.json()["id"]

        return await _poll_until_terminal(
            client,
            base=base,
            headers=headers,
            task_id=task_id,
            task_description=descriptor["task"],
            timeout_seconds=descriptor["timeout_seconds"],
            poll_interval_seconds=poll_interval_seconds,
        )


async def _poll_until_terminal(
    client: httpx.AsyncClient,
    *,
    base: str,
    headers: dict[str, str],
    task_id: str,
    task_description: str,
    timeout_seconds: int,
    poll_interval_seconds: int,
) -> Any:
    """Long-poll the awaithumans server until terminal, then return
    the response (or raise the typed error matching the status)."""
    while True:
        resp = await client.get(
            f"{base}/api/tasks/{task_id}/poll",
            params={"timeout": poll_interval_seconds},
            headers=headers,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"awaithumans poll failed for task {task_id} "
                f"(HTTP {resp.status_code}): {resp.text[:500]}"
            )
        data = resp.json()
        status = data.get("status")
        if status == "completed":
            return data.get("response")
        if status == "timed_out":
            raise TaskTimeoutError(task=task_description, timeout_seconds=timeout_seconds)
        if status == "cancelled":
            raise TaskCancelledError(task_description)
        if status == "verification_exhausted":
            raise VerificationExhaustedError(
                task_description, data.get("verification_attempt", 0)
            )
        # Non-terminal — long-poll returned because of its own timeout
        # (default 25s). Reconnect and try again. No sleep: the server
        # holds the connection so we're not in a tight loop.
        logger.debug("Task %s still pending, reconnecting", task_id)
