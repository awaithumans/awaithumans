"""Core client — await_human() async and await_human_sync()."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import TypeVar

import httpx
from pydantic import BaseModel

from awaithumans.errors import (
    MarketplaceNotAvailableError,
    SchemaValidationError,
    TimeoutRangeError,
)
from awaithumans.types import MarketplaceAssignment

T = TypeVar("T", bound=BaseModel)

MIN_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 2_592_000  # 30 days


async def await_human(
    *,
    task: str,
    payload_schema: type[T],
    payload: BaseModel,
    response_schema: type[T],
    timeout_seconds: int,
    assign_to: object | None = None,
    notify: list[str] | None = None,
    verifier: object | None = None,
    idempotency_key: str | None = None,
    redact_payload: bool = False,
    server_url: str | None = None,
) -> T:
    """
    Delegate a task to a human and await the result (async).

    Direct mode: long-polls the server until the human completes or timeout.
    For durable mode, use awaithumans.temporal or awaithumans.langgraph instead.
    """
    # ── Validate timeout range ───────────────────────────────────────
    if timeout_seconds < MIN_TIMEOUT_SECONDS or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise TimeoutRangeError(timeout_seconds)

    # ── Validate payload against schema ──────────────────────────────
    try:
        payload_schema.model_validate(payload.model_dump())
    except Exception as e:
        raise SchemaValidationError("payload", str(e)) from e

    # ── Check for reserved marketplace ───────────────────────────────
    if isinstance(assign_to, MarketplaceAssignment):
        raise MarketplaceNotAvailableError()

    # ── Generate idempotency key ─────────────────────────────────────
    key = idempotency_key or _generate_idempotency_key(task, payload)

    # ── Convert schemas to JSON Schema ───────────────────────────────
    payload_json_schema = payload_schema.model_json_schema()
    response_json_schema = response_schema.model_json_schema()

    # ── Resolve server URL ───────────────────────────────────────────
    url = server_url or os.environ.get("AWAITHUMANS_URL", "http://localhost:3001")

    # ── Create task on the server ────────────────────────────────────
    # TODO: POST {url}/api/tasks
    # Body: { task, payload, payload_schema, response_schema, timeout_seconds,
    #         assign_to, notify, idempotency_key, verifier, redact_payload }
    # Returns: { task_id }

    # ── Long-poll until completion or timeout ────────────────────────
    # TODO: GET {url}/api/tasks/{task_id}/poll
    # Reconnect every ~25s to stay under gateway timeouts.
    # On completion: validate response against response_schema, return typed result.
    # On timeout: raise TimeoutError.
    # On verification_exhausted: raise VerificationExhaustedError.

    # ── Placeholder ──────────────────────────────────────────────────
    _ = key, payload_json_schema, response_json_schema, url, notify, verifier, redact_payload
    raise NotImplementedError("Server client not yet implemented — awaiting server build.")


def await_human_sync(
    *,
    task: str,
    payload_schema: type[BaseModel],
    payload: BaseModel,
    response_schema: type[BaseModel],
    timeout_seconds: int,
    assign_to: object | None = None,
    notify: list[str] | None = None,
    verifier: object | None = None,
    idempotency_key: str | None = None,
    redact_payload: bool = False,
    server_url: str | None = None,
) -> BaseModel:
    """
    Delegate a task to a human and block until the result (sync).

    Convenience wrapper for sync code (Flask, Celery, LangChain pre-v0.3).
    Runs await_human() in a new event loop on a background thread.
    """
    return asyncio.run(
        await_human(
            task=task,
            payload_schema=payload_schema,
            payload=payload,
            response_schema=response_schema,
            timeout_seconds=timeout_seconds,
            assign_to=assign_to,
            notify=notify,
            verifier=verifier,
            idempotency_key=idempotency_key,
            redact_payload=redact_payload,
            server_url=server_url,
        )
    )


def _generate_idempotency_key(task: str, payload: BaseModel) -> str:
    """Generate a deterministic key from task + payload using canonical JSON."""
    canonical = json.dumps(
        {"task": task, "payload": payload.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]
