"""Core client — await_human() async and await_human_sync()."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from typing import TypeVar

import httpx
from pydantic import BaseModel

from awaithumans.errors import (
    AwaitHumansError,
    MarketplaceNotAvailableError,
    SchemaValidationError,
    TaskTimeoutError,
    TimeoutRangeError,
    VerificationExhaustedError,
)
from awaithumans.types import MarketplaceAssignment, VerifierConfig
from awaithumans.utils.constants import (
    MAX_TIMEOUT_SECONDS,
    MIN_TIMEOUT_SECONDS,
    POLL_INTERVAL_SECONDS_SECONDS,
)

logger = logging.getLogger("awaithumans.client")

T = TypeVar("T", bound=BaseModel)


async def await_human(
    *,
    task: str,
    payload_schema: type[T],
    payload: BaseModel,
    response_schema: type[T],
    timeout_seconds: int,
    assign_to: object | None = None,
    notify: list[str] | None = None,
    verifier: VerifierConfig | None = None,
    idempotency_key: str | None = None,
    redact_payload: bool = False,
    server_url: str | None = None,
) -> T:
    """
    Delegate a task to a human and await the result (async).

    Direct mode: creates a task on the server, then long-polls until the
    human completes it or the timeout expires.

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

    # ── Resolve server URL ───────────────────────────────────────────
    base_url = (server_url or os.environ.get("AWAITHUMANS_URL", "http://localhost:3001")).rstrip("/")

    # ── Serialize assign_to for the wire ─────────────────────────────
    assign_to_dict = None
    if assign_to is not None:
        if isinstance(assign_to, str):
            assign_to_dict = {"email": assign_to}
        elif isinstance(assign_to, list):
            assign_to_dict = {"emails": assign_to}
        elif isinstance(assign_to, BaseModel):
            assign_to_dict = assign_to.model_dump()
        else:
            assign_to_dict = {"value": str(assign_to)}

    # ── Create task on the server ────────────────────────────────────
    async with httpx.AsyncClient(timeout=30) as client:
        create_body = {
            "task": task,
            "payload": payload.model_dump(mode="json"),
            "payload_schema": payload_schema.model_json_schema(),
            "response_schema": response_schema.model_json_schema(),
            "timeout_seconds": timeout_seconds,
            "idempotency_key": key,
            "assign_to": assign_to_dict,
            "notify": notify,
            "verifier_config": verifier.model_dump() if verifier else None,
            "redact_payload": redact_payload,
        }

        resp = await client.post(f"{base_url}/api/tasks", json=create_body)
        if resp.status_code not in (200, 201):
            raise AwaitHumansError(
                code="TASK_CREATE_FAILED",
                message=f"Failed to create task on the server (HTTP {resp.status_code}).",
                hint=f"Server response: {resp.text[:500]}",
                docs_url="https://awaithumans.dev/docs/troubleshooting#task-create-failed",
            )

        task_data = resp.json()
        task_id = task_data["id"]
        logger.info("Task created: %s (idempotency_key=%s)", task_id, key)

    # ── Long-poll until completion or timeout ────────────────────────
    result = await _poll_until_terminal(base_url, task_id, task, timeout_seconds, response_schema)
    return result


async def _poll_until_terminal(
    base_url: str,
    task_id: str,
    task_description: str,
    timeout_seconds: int,
    response_schema: type[T],
) -> T:
    """Long-poll the server until the task reaches a terminal state.

    Reconnects every POLL_INTERVAL_SECONDS seconds to stay under gateway timeouts.
    The server's poll endpoint holds the connection for up to 25 seconds
    per request.
    """
    async with httpx.AsyncClient(timeout=POLL_INTERVAL_SECONDS + 10) as client:
        while True:
            resp = await client.get(
                f"{base_url}/api/tasks/{task_id}/poll",
                params={"timeout": POLL_INTERVAL_SECONDS},
            )

            if resp.status_code == 404:
                raise AwaitHumansError(
                    code="TASK_NOT_FOUND",
                    message=f"Task '{task_id}' not found on the server.",
                    hint="The task may have been deleted or the server was restarted with a fresh database.",
                    docs_url="https://awaithumans.dev/docs/troubleshooting#task-not-found",
                )

            if resp.status_code != 200:
                raise AwaitHumansError(
                    code="POLL_FAILED",
                    message=f"Failed to poll task '{task_id}' (HTTP {resp.status_code}).",
                    hint=f"Server response: {resp.text[:500]}",
                    docs_url="https://awaithumans.dev/docs/troubleshooting#poll-failed",
                )

            poll_data = resp.json()
            status = poll_data["status"]

            if status == "completed":
                raw_response = poll_data["response"]
                logger.info("Task %s completed", task_id)
                # Validate response against schema and return typed result
                try:
                    return response_schema.model_validate(raw_response)
                except Exception as e:
                    raise SchemaValidationError("response", str(e)) from e

            if status == "timed_out":
                raise TaskTimeoutError(task_description, timeout_seconds)

            if status == "cancelled":
                raise AwaitHumansError(
                    code="TASK_CANCELLED",
                    message=f"Task '{task_description}' was cancelled.",
                    hint="The task was cancelled by an admin or another agent.",
                    docs_url="https://awaithumans.dev/docs/troubleshooting#task-cancelled",
                )

            if status == "verification_exhausted":
                raise VerificationExhaustedError(
                    task_description,
                    poll_data.get("verification_attempt", 0),
                )

            # Non-terminal status — the server's poll timed out (25s).
            # Reconnect and poll again.
            logger.debug("Task %s still pending (status=%s), reconnecting...", task_id, status)


def await_human_sync(
    *,
    task: str,
    payload_schema: type[T],
    payload: BaseModel,
    response_schema: type[T],
    timeout_seconds: int,
    assign_to: object | None = None,
    notify: list[str] | None = None,
    verifier: VerifierConfig | None = None,
    idempotency_key: str | None = None,
    redact_payload: bool = False,
    server_url: str | None = None,
) -> T:
    """
    Delegate a task to a human and block until the result (sync).

    Convenience wrapper for sync code (Flask, Celery, LangChain pre-v0.3).
    Runs await_human() in a new event loop.
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
